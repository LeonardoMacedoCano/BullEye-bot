import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import defer, followup, mention, perf_start, perf_log

from bot.db.repository import (
    get_or_create_user, list_tickers, update_ticker_subcategory, get_proventos_upcoming,
)
from bot.services.market import (
    get_ticker_data, get_ticker_subcategory, get_br_stock_metrics, get_dividend_info,
    SUBCATEGORY_ORDER, SUBCATEGORY_LABELS,
)
from bot.services.fear_greed import get_fear_greed_index
from bot.services.sentiment import get_vix, get_ibov

logger = logging.getLogger(__name__)

_MSG_LIMIT = 1900


def _display_name(ticker: str) -> str:
    if ticker.upper() == "BTC-USD":
        return "BTC"
    return ticker[:-3] if ticker.upper().endswith(".SA") else ticker


def _currency(ticker: str) -> str:
    return "R$" if ticker.upper().endswith(".SA") else "$"


def _fmt(value: float, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def _fmt_pct(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.1f}%"


def _fmt_ceiling(ceiling: float | None, current_price: float, sym: str) -> str:
    if ceiling is None:
        return "—"
    m = (ceiling - current_price) / current_price * 100
    sign = "+" if m >= 0 else ""
    return f"{sym}{ceiling:,.2f} {sign}{m:.0f}%"


def _render_table(
    headers: list[str],
    rows: list[list[str]],
    required_headers: list[str] | None = None,
) -> str:
    required = set(required_headers or [])
    active = [
        i for i in range(len(headers))
        if headers[i] in required or any(r[i] != "—" for r in rows)
    ]
    if not active:
        return ""
    widths = [
        max(len(headers[i]), max((len(r[i]) for r in rows), default=0)) + 1
        for i in active
    ]
    header_line = "".join(f"{headers[i]:<{w}}" for i, w in zip(active, widths))
    sep = "─" * sum(widths)
    data_lines = [
        "".join(f"{r[i]:<{w}}" for i, w in zip(active, widths))
        for r in rows
    ]
    return "\n".join([header_line, sep] + data_lines)


def _collect_rows(group_rows: list, show_br: bool) -> tuple[list[str], list[list[str]]]:
    data_rows: list[list[str]] = []

    if show_br:
        headers = ["Ticker", "Price", "Day%", "DY%", "Ceiling"]
        for row in group_rows:
            ticker = row["ticker"]
            name = _display_name(ticker)
            sym = _currency(ticker)
            try:
                ceiling_val = row["user_ceiling"]
            except (KeyError, IndexError):
                ceiling_val = None
            market = get_ticker_data(ticker)
            if not market:
                data_rows.append([name, "—", "—", "—", "—"])
                continue
            cp = market["current_price"]
            day_str = _fmt_pct(market.get("day_change_pct", 0.0))
            m = get_br_stock_metrics(ticker, cp)
            dy_str = f"{m['dy_yield']*100:.2f}%" if m["dy_yield"] > 0 else "—"
            data_rows.append([name, _fmt(cp, sym), day_str, dy_str, _fmt_ceiling(ceiling_val, cp, sym)])
    else:
        headers = ["Ticker", "Price", "Day%", "Ceiling"]
        for row in group_rows:
            ticker = row["ticker"]
            name = _display_name(ticker)
            sym = _currency(ticker)
            try:
                ceiling_val = row["user_ceiling"]
            except (KeyError, IndexError):
                ceiling_val = None
            market = get_ticker_data(ticker)
            if not market:
                data_rows.append([name, "—", "—", "—"])
                continue
            cp = market["current_price"]
            day_str = _fmt_pct(market.get("day_change_pct", 0.0))
            data_rows.append([name, _fmt(cp, sym), day_str, _fmt_ceiling(ceiling_val, cp, sym)])

    return headers, data_rows


def _group_by_subcategory(rows: list) -> list[tuple[str | None, list]]:
    groups: dict[str | None, list] = {}
    for row in rows:
        try:
            key = row["subcategory"]
        except (IndexError, KeyError):
            key = None
        if key not in groups:
            groups[key] = []
        groups[key].append(row)

    ordered = []
    for key in SUBCATEGORY_ORDER:
        if key in groups:
            ordered.append((key, groups[key]))
    for key, vals in groups.items():
        if key is not None and key not in SUBCATEGORY_ORDER:
            ordered.append((key, vals))
    if None in groups:
        ordered.append((None, groups[None]))
    return ordered


def _build_section(title: str, rows: list) -> list[str]:
    groups = _group_by_subcategory(rows)
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
        table_str = _render_table(headers, data_rows)
        if not table_str:
            continue

        full_block = _block(table_str, label, not heading_emitted)

        if len(full_block) <= _MSG_LIMIT:
            if not heading_emitted:
                messages.append(full_block)
                heading_emitted = True
            else:
                plain = _block(table_str, label, False)
                if messages and len(messages[-1]) + 1 + len(plain) <= _MSG_LIMIT:
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
                if len(_block(candidate_tbl, chunk_label, chunk_with_cat)) > _MSG_LIMIT and batch:
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


def _pack_messages(sections: list[str]) -> list[str]:
    packed: list[str] = []
    current = ""
    for s in sections:
        if not current:
            current = s
        elif len(current) + 1 + len(s) <= _MSG_LIMIT:
            current += "\n" + s
        else:
            packed.append(current)
            current = s
    if current:
        packed.append(current)
    return packed


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
            f"{vix['level']:.1f}", _fmt_pct(vix['day_change_pct']), vix['status'],
        ])
    if ibov:
        data_rows.append([
            "IBOV", "Bovespa Index", "BR/Stocks",
            f"{ibov['level']:,.0f}", _fmt_pct(ibov['day_change_pct']), "—",
        ])
    if has_btc and fg:
        data_rows.append([
            "F&G", "Fear & Greed", "Crypto/BTC",
            str(fg['value']), "—", fg['classification'],
        ])

    table_str = _render_table(headers, data_rows)
    msg = f"# 📊 Market Indicators\n```\n{table_str}\n```"
    return [msg] if len(msg) <= _MSG_LIMIT else [msg[:_MSG_LIMIT]]


def _build_performance(wallet: list, watchlist: list) -> list[str]:
    def _get_movers(rows: list) -> list[dict]:
        out = []
        for row in rows:
            data = get_ticker_data(row["ticker"])
            if data:
                out.append({
                    "name":  _display_name(row["ticker"]),
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
            all_bd.append(f"▲ {best['name']} {_fmt_pct(best[key])}")
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
                lines.append(f"  {period_label:<7}{arrow} {best['name']} {_fmt_pct(best[key])}")
            else:
                show_best  = best[key] > 0
                show_worst = worst[key] < 0
                if not show_best and not show_worst:
                    continue
                bd = f"▲ {best['name']} {_fmt_pct(best[key])}"
                wd = f"▼ {worst['name']} {_fmt_pct(worst[key])}"
                if show_best and show_worst:
                    lines.append(f"  {period_label:<7}{bd:<{COL}}{wd}")
                elif show_best:
                    lines.append(f"  {period_label:<7}{bd}")
                else:
                    lines.append(f"  {period_label:<7}{wd}")

    table = "\n".join(lines)
    msg = f"# 📈 Performance\n```\n{table}\n```"
    return [msg] if len(msg) <= _MSG_LIMIT else [msg[:_MSG_LIMIT]]


def _build_proventos_radar(tickers: list) -> list[str]:
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
    if not db_rows:
        return []

    def _fmt_date(d: str | None) -> str:
        return d.replace("-", "/") if d else "—"

    headers = ["Ticker", "Ex-Date", "Pay-Date", "Type", "Amount"]
    data_rows: list[list[str]] = []
    for row in db_rows:
        ticker = row["symbol"]
        sym = _currency(ticker)
        name = _display_name(ticker)
        ex_d = _fmt_date(row["ex_date"])
        pay_d = _fmt_date(row["pay_date"])
        ptype = row["type"] or "—"
        amount = row["amount"]
        amt_str = f"{sym}{amount:,.2f}" if amount else "—"
        data_rows.append([name, ex_d, pay_d, ptype, amt_str])

    table_str = _render_table(headers, data_rows, required_headers=["Pay-Date", "Type"])
    if not table_str:
        return []
    msg = f"# 📅 Dividends\n```\n{table_str}\n```"
    return [msg] if len(msg) <= _MSG_LIMIT else [msg[:_MSG_LIMIT]]


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
        sym = _currency(ticker)
        name = _display_name(ticker)
        data_rows.append([
            name,
            _fmt(opp["current_price"], sym),
            _fmt(opp["user_ceiling"], sym),
            f"+{opp['margin_pct']:.1f}%",
            opp["category"],
        ])

    table_str = _render_table(headers, data_rows)
    msg = f"# 🛒 Buy Opportunities\n```\n{table_str}\n```"
    return [msg] if len(msg) <= _MSG_LIMIT else [msg[:_MSG_LIMIT]]


def build_summary(user_id: int, discord_mention: str) -> list[str]:
    tickers = list_tickers(user_id)
    if not tickers:
        return [f"{discord_mention} You have no tickers configured. Use `/add <TICKER>` to get started."]

    tickers = _backfill_subcategories(user_id, tickers)
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
    sections.extend(_build_proventos_radar(tickers))
    sections.extend(_build_opportunities(tickers))

    if not sections:
        return [f"{discord_mention} Could not fetch data for your tickers."]

    packed = _pack_messages(sections)
    packed[0] = f"{discord_mention} Your summary:\n{packed[0]}"
    return packed


class SummaryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="summary", description="Get your current portfolio summary")
    async def summary(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        async with self.bot.heavy_semaphore:
            try:
                messages = await asyncio.wait_for(
                    loop.run_in_executor(None, build_summary, user["id"], m),
                    timeout=120.0,
                )
                for msg in messages:
                    await followup(interaction, msg)
                logger.info("Summary sent to user %s", interaction.user.id)
                perf_log(logger, "summary", t0)
            except asyncio.TimeoutError:
                await followup(interaction, f"{m} ❌ Summary timed out. Please try again.")
            except Exception:
                logger.exception("Error in summary for user %s", interaction.user.id)
                await followup(interaction, f"{m} ❌ Error generating summary. Please try again.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummaryCog(bot))
