import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from bot.db.repository import get_or_create_user, list_tickers, update_ticker_subcategory
from bot.services.market import get_ticker_data, get_ticker_subcategory, SUBCATEGORY_ORDER, SUBCATEGORY_LABELS
from bot.application.market_cache import get_br_stock_metrics
from bot.application.dividends_use_case import build_proventos_radar
from bot.services.fear_greed import get_fear_greed_index
from bot.services.sentiment import get_vix, get_ibov
from bot.shared.formatting import (
    MSG_LIMIT, display_name, currency, fmt, fmt_pct,
    render_table, pack_messages, group_by_subcategory,
)

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
            day_str = fmt_pct(market.get("day_change_pct", 0.0))
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
            day_str = fmt_pct(market.get("day_change_pct", 0.0))
            data_rows.append([name, fmt(cp, sym), day_str, _fmt_ceiling(ceiling_val, cp, sym)])

    return headers, data_rows


def _build_section(title: str, rows: list) -> list[str]:
    groups = group_by_subcategory(rows, SUBCATEGORY_ORDER)
    if not (len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)):
        groups = [(None, rows)]

    messages: list[str] = []
    heading_emitted = False

    def _block(tbl: str, lbl: str | None, with_cat: bool) -> str:
        parts = [f"# {title}"] if with_cat else []
        if lbl:
            parts.append(f"- **{lbl}**")
        parts.append(f"```\n{tbl}\n```")
        return "\n".join(parts)

    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None
        show_br = key == "br-stocks"
        headers, data_rows = _collect_rows(group_rows, show_br)
        table_str = render_table(headers, data_rows)
        if not table_str:
            continue

        full_block = _block(table_str, label, not heading_emitted)

        if len(full_block) <= MSG_LIMIT:
            if not heading_emitted:
                messages.append(full_block)
                heading_emitted = True
            else:
                plain = _block(table_str, label, False)
                if messages and len(messages[-1]) + 1 + len(plain) <= MSG_LIMIT:
                    messages[-1] += "\n" + plain
                else:
                    messages.append(plain)
        else:
            table_lines = table_str.split("\n")
            header_block = "\n".join(table_lines[:2])
            batch: list[str] = []
            chunk_label = label
            chunk_with_cat = not heading_emitted

            for dl in table_lines[2:]:
                candidate_tbl = header_block + "\n" + "\n".join(batch + [dl])
                if len(_block(candidate_tbl, chunk_label, chunk_with_cat)) > MSG_LIMIT and batch:
                    done_tbl = header_block + "\n" + "\n".join(batch)
                    messages.append(_block(done_tbl, chunk_label, chunk_with_cat))
                    heading_emitted = True
                    chunk_with_cat = False
                    chunk_label = f"{label} (cont.)" if label else None
                    batch = [dl]
                else:
                    batch.append(dl)

            if batch:
                done_tbl = header_block + "\n" + "\n".join(batch)
                messages.append(_block(done_tbl, chunk_label, chunk_with_cat))
                heading_emitted = True

    return messages


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


def _build_market_indicators(has_btc: bool, fg: dict | None) -> list[str]:
    vix = get_vix()
    ibov = get_ibov()
    if not vix and not ibov and not (has_btc and fg):
        return []

    headers = ["Index", "Description", "Region", "Value", "Day%", "Status"]
    data_rows: list[list[str]] = []
    if vix:
        data_rows.append([
            "VIX", "Volatility Index", "Global",
            f"{vix['level']:.1f}", fmt_pct(vix['day_change_pct']), vix['status'],
        ])
    if ibov:
        data_rows.append([
            "IBOV", "Bovespa Index", "BR/Stocks",
            f"{ibov['level']:,.0f}", fmt_pct(ibov['day_change_pct']), "—",
        ])
    if has_btc and fg:
        data_rows.append([
            "F&G", "Fear & Greed", "Crypto/BTC",
            str(fg['value']), "—", fg['classification'],
        ])

    table_str = render_table(headers, data_rows)
    msg = f"# 📊 Market Indicators\n```\n{table_str}\n```"
    return [msg] if len(msg) <= MSG_LIMIT else [msg[:MSG_LIMIT]]


def _build_performance(wallet: list, watchlist: list) -> list[str]:
    def _get_movers(rows: list) -> list[dict]:
        out = []
        for row in rows:
            data = get_ticker_data(row["ticker"])
            if data:
                out.append({
                    "name":  display_name(row["ticker"]),
                    "day":   data.get("day_change_pct", 0.0),
                    "week":  data.get("week_change_pct", 0.0),
                    "month": data.get("month_change_pct", 0.0),
                })
        return out

    groups: list[tuple[str, list]] = []
    for label, rows in [("Wallet", wallet), ("Watchlist", watchlist)]:
        if rows:
            movers = _get_movers(rows)
            if movers:
                groups.append((label, movers))

    if not groups:
        return []

    all_bd: list[str] = []
    for _, items in groups:
        for _, key in [("Day:", "day"), ("Week:", "week"), ("Month:", "month")]:
            best = max(items, key=lambda x: x[key])
            all_bd.append(f"▲ {best['name']} {fmt_pct(best[key])}")
    COL = max(len(s) for s in all_bd) + 2

    lines: list[str] = []

    for label, items in groups:
        if len(groups) > 1:
            lines.append(label)
        for period_label, key in [("Day:", "day"), ("Week:", "week"), ("Month:", "month")]:
            best  = max(items, key=lambda x: x[key])
            worst = min(items, key=lambda x: x[key])
            if worst["name"] == best["name"]:
                arrow = "▲" if best[key] >= 0 else "▼"
                lines.append(f"  {period_label:<7}{arrow} {best['name']} {fmt_pct(best[key])}")
            else:
                show_best  = best[key] > 0
                show_worst = worst[key] < 0
                if not show_best and not show_worst:
                    continue
                bd = f"▲ {best['name']} {fmt_pct(best[key])}"
                wd = f"▼ {worst['name']} {fmt_pct(worst[key])}"
                if show_best and show_worst:
                    lines.append(f"  {period_label:<7}{bd:<{COL}}{wd}")
                elif show_best:
                    lines.append(f"  {period_label:<7}{bd}")
                else:
                    lines.append(f"  {period_label:<7}{wd}")

    table = "\n".join(lines)
    msg = f"# 📈 Performance\n```\n{table}\n```"
    return [msg] if len(msg) <= MSG_LIMIT else [msg[:MSG_LIMIT]]


def _build_opportunities(tickers: list) -> list[str]:
    opportunities = []
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
            margin = (user_ceiling - data["current_price"]) / data["current_price"] * 100
            opportunities.append({
                "ticker": row["ticker"],
                "current_price": data["current_price"],
                "user_ceiling": user_ceiling,
                "margin_pct": margin,
                "category": row["category"],
            })

    if not opportunities:
        return []

    opportunities.sort(key=lambda x: x["margin_pct"], reverse=True)

    headers = ["Ticker", "Price", "Ceiling", "Margin", "In"]
    data_rows = []
    for opp in opportunities:
        ticker = opp["ticker"]
        sym = currency(ticker)
        name = display_name(ticker)
        data_rows.append([
            name,
            fmt(opp["current_price"], sym),
            fmt(opp["user_ceiling"], sym),
            f"+{opp['margin_pct']:.1f}%",
            opp["category"],
        ])

    table_str = render_table(headers, data_rows)
    msg = f"# 🛒 Buy Opportunities\n```\n{table_str}\n```"
    return [msg] if len(msg) <= MSG_LIMIT else [msg[:MSG_LIMIT]]


def _prefetch_tickers(tickers: list) -> None:
    """Warm the price cache for all tickers concurrently before building sections."""
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


def build_summary(user_id: int, discord_mention: str) -> list[str]:
    tickers = list_tickers(user_id)
    if not tickers:
        return [f"{discord_mention} You have no tickers configured. Use `/add <TICKER>` to get started."]

    tickers = _backfill_subcategories(user_id, tickers)
    _prefetch_tickers(tickers)
    wallet    = [row for row in tickers if row["category"] == "wallet"]
    watchlist = [row for row in tickers if row["category"] == "watchlist"]
    has_btc   = any(row["ticker"].upper() == "BTC-USD" for row in tickers)

    fg = get_fear_greed_index() if has_btc else None

    sections: list[str] = []
    if wallet:
        sections.extend(_build_section("💼 Wallet", wallet))
    if watchlist:
        sections.extend(_build_section("👀 Watchlist", watchlist))
    sections.extend(_build_market_indicators(has_btc, fg))
    sections.extend(_build_performance(wallet, watchlist))
    sections.extend(build_proventos_radar(tickers))
    sections.extend(_build_opportunities(tickers))

    if not sections:
        return [f"{discord_mention} Could not fetch data for your tickers."]

    packed = pack_messages(sections)
    packed[0] = f"{discord_mention} Your summary:\n{packed[0]}"
    return packed
