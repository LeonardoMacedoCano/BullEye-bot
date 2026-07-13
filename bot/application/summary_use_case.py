import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from bot.db.repository import (
    list_tickers, update_ticker_subcategory, get_user_fgi_ceiling, get_proventos_upcoming,
)
from bot.services.market import get_ticker_data, get_ticker_subcategory, SUBCATEGORY_ORDER, SUBCATEGORY_LABELS
from bot.application.market_cache import get_br_stock_metrics, get_dividend_info
from bot.services.fear_greed import get_fear_greed_index
from bot.services.sentiment import get_vix, get_ibov
from bot.shared.formatting import display_name, currency, fmt, fmt_pct, ansi_pct, render_table, group_by_subcategory

logger = logging.getLogger(__name__)


def _fmt_ceiling(ceiling: float | None, current_price: float, sym: str) -> str:
    if ceiling is None:
        return "—"
    m = (ceiling - current_price) / current_price * 100
    sign = "+" if m >= 0 else ""
    return f"{sym}{ceiling:,.2f} {sign}{m:.0f}%"


def _collect_rows(group_rows: list, show_br: bool) -> tuple[list[str], list[list[str]]]:
    data_rows: list[list[str]] = []

    if show_br:
        headers = ["Ticker", "Price", "Day%", "DY%", "Ceiling"]
        for row in group_rows:
            ticker = row["ticker"]
            name = display_name(ticker)
            sym = currency(ticker)
            try:
                ceiling_val = row["user_ceiling"]
            except (KeyError, IndexError):
                ceiling_val = None
            market = get_ticker_data(ticker)
            if not market:
                data_rows.append([name, "—", "—", "—", "—"])
                continue
            cp = market["current_price"]
            day_str = ansi_pct(market.get("day_change_pct", 0.0))
            m = get_br_stock_metrics(ticker, cp)
            dy_str = f"{m['dy_yield']*100:.2f}%" if m["dy_yield"] > 0 else "—"
            data_rows.append([name, fmt(cp, sym), day_str, dy_str, _fmt_ceiling(ceiling_val, cp, sym)])
    else:
        headers = ["Ticker", "Price", "Day%", "Ceiling"]
        for row in group_rows:
            ticker = row["ticker"]
            name = display_name(ticker)
            sym = currency(ticker)
            try:
                ceiling_val = row["user_ceiling"]
            except (KeyError, IndexError):
                ceiling_val = None
            market = get_ticker_data(ticker)
            if not market:
                data_rows.append([name, "—", "—", "—"])
                continue
            cp = market["current_price"]
            day_str = ansi_pct(market.get("day_change_pct", 0.0))
            data_rows.append([name, fmt(cp, sym), day_str, _fmt_ceiling(ceiling_val, cp, sym)])

    return headers, data_rows


def _get_section_groups(rows: list) -> list[dict]:
    groups = group_by_subcategory(rows, SUBCATEGORY_ORDER)
    if not (len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)):
        groups = [(None, rows)]

    result = []
    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None
        show_br = key == "br-stocks"
        headers, data_rows = _collect_rows(group_rows, show_br)
        table_str = render_table(headers, data_rows)
        if table_str:
            result.append({"label": label, "table_str": table_str, "is_br": show_br})
    return result


def _get_market_data(has_btc: bool, fg: dict | None, fgi_ceiling: int | None) -> dict | None:
    vix = get_vix()
    ibov = get_ibov()
    if not vix and not ibov and not (has_btc and fg):
        return None
    return {
        "vix": vix,
        "ibov": ibov,
        "fgi": {**fg, "fgi_ceiling": fgi_ceiling} if has_btc and fg else None,
    }


def _get_performance_data(wallet: list, watchlist: list) -> dict | None:
    def _get_movers(rows: list) -> list[dict]:
        out = []
        for row in rows:
            data = get_ticker_data(row["ticker"])
            if data:
                out.append({
                    "name": display_name(row["ticker"]),
                    "day": data.get("day_change_pct", 0.0),
                    "week": data.get("week_change_pct", 0.0),
                    "month": data.get("month_change_pct", 0.0),
                })
        return out

    groups = []
    for label, rows in [("Wallet", wallet), ("Watchlist", watchlist)]:
        if not rows:
            continue
        movers = _get_movers(rows)
        if not movers:
            continue
        periods = []
        for period_key, period_label in [("day", "Day"), ("week", "Week"), ("month", "Month")]:
            best = max(movers, key=lambda x: x[period_key])
            worst = min(movers, key=lambda x: x[period_key])
            periods.append({
                "label": period_label,
                "best": {"name": best["name"], "value": best[period_key]},
                "worst": {"name": worst["name"], "value": worst[period_key]},
                "same": best["name"] == worst["name"],
            })
        groups.append({"label": label, "periods": periods})

    return {"groups": groups} if groups else None


def _get_dividends_rows(tickers: list) -> list[dict]:
    for row in tickers:
        ticker = row["ticker"]
        if ticker.upper().endswith(".SA"):
            data = get_ticker_data(ticker)
            if data:
                get_br_stock_metrics(ticker, data["current_price"])
        else:
            get_dividend_info(ticker)

    ticker_names = [row["ticker"] for row in tickers]
    db_rows = get_proventos_upcoming(ticker_names)

    result = []
    for row in db_rows:
        ticker = row["symbol"]
        sym = currency(ticker)
        name = display_name(ticker)
        ex_d = row["ex_date"].replace("-", "/") if row["ex_date"] else "—"
        pay_d = row["pay_date"].replace("-", "/") if row["pay_date"] else "—"
        amount = row["amount"]
        amt_str = f"{sym}{amount:,.2f}" if amount else "—"
        result.append({
            "name": name,
            "ex_date": ex_d,
            "pay_date": pay_d,
            "type": row["type"] or "—",
            "amount": amt_str,
        })
    return result


def _get_opportunities_data(tickers: list, fg: dict | None, fgi_ceiling: int | None) -> dict:
    ticker_opps = []
    for row in tickers:
        try:
            user_ceiling = row["user_ceiling"]
        except (KeyError, IndexError):
            continue
        if user_ceiling is None:
            continue
        data = get_ticker_data(row["ticker"])
        if not data:
            continue
        if data["current_price"] <= user_ceiling:
            sym = currency(row["ticker"])
            margin = (user_ceiling - data["current_price"]) / data["current_price"] * 100
            ticker_opps.append({
                "name": display_name(row["ticker"]),
                "price": fmt(data["current_price"], sym),
                "ceiling": fmt(user_ceiling, sym),
                "margin": f"+{margin:.1f}%",
                "category": row["category"],
            })

    ticker_opps.sort(key=lambda x: float(x["margin"][1:-1]), reverse=True)

    fgi_triggered = bool(fg and fgi_ceiling is not None and fg["value"] <= fgi_ceiling)
    fgi_data = None
    if fgi_triggered:
        fgi_data = {
            "value": fg["value"],
            "ceiling": fgi_ceiling,
            "classification": fg["classification"],
        }

    return {"ticker_opps": ticker_opps, "fgi_triggered": fgi_triggered, "fgi_data": fgi_data}


def _compute_avg_day_change(rows: list) -> float | None:
    changes = [
        data.get("day_change_pct", 0.0)
        for row in rows
        if (data := get_ticker_data(row["ticker"])) is not None
    ]
    return sum(changes) / len(changes) if changes else None


def _backfill_subcategories(user_id: int, tickers: list) -> list:
    result = []
    for row in tickers:
        if row["subcategory"] is None:
            sub = get_ticker_subcategory(row["ticker"])
            update_ticker_subcategory(user_id, row["ticker"], sub)
            result.append({**dict(row), "subcategory": sub})
        else:
            result.append(row)
    return result


def _prefetch_tickers(tickers: list) -> None:
    unique = list({row["ticker"] for row in tickers})
    if not unique:
        return
    workers = min(len(unique), 10)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(get_ticker_data, t) for t in unique]
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass


def build_summary(user_id: int, discord_mention: str) -> dict:
    tickers = list_tickers(user_id)
    if not tickers:
        return {"empty": True, "mention": discord_mention}

    tickers = _backfill_subcategories(user_id, tickers)
    _prefetch_tickers(tickers)
    wallet = [row for row in tickers if row["category"] == "wallet"]
    watchlist = [row for row in tickers if row["category"] == "watchlist"]
    has_btc = any(row["ticker"].upper() == "BTC-USD" for row in tickers)

    fg = get_fear_greed_index() if has_btc else None
    fgi_ceiling = get_user_fgi_ceiling(user_id)

    return {
        "empty": False,
        "mention": discord_mention,
        "wallet_groups": _get_section_groups(wallet),
        "watchlist_groups": _get_section_groups(watchlist),
        "avg_day_change": _compute_avg_day_change(wallet),
        "market": _get_market_data(has_btc, fg, fgi_ceiling),
        "performance": _get_performance_data(wallet, watchlist),
        "dividends": _get_dividends_rows(tickers),
        "opportunities": _get_opportunities_data(tickers, fg, fgi_ceiling),
    }
