import logging
import discord
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers, update_ticker_subcategory
from bot.services.market import (
    get_ticker_data, get_ticker_subcategory, get_br_stock_metrics,
    SUBCATEGORY_ORDER, SUBCATEGORY_LABELS,
)
from bot.services.fear_greed import get_fear_greed_index

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


def _fmt_ceiling(ceiling: float | None, current_price: float, sym: str) -> str:
    if ceiling is None:
        return "—"
    m = (ceiling - current_price) / current_price * 100
    sign = "+" if m >= 0 else ""
    return f"{sym}{ceiling:,.2f} {sign}{m:.0f}%"


def _render_table(headers: list[str], rows: list[list[str]]) -> str:
    """Dynamic column widths; skips columns where every value is '—'."""
    active = [i for i in range(len(headers)) if any(r[i] != "—" for r in rows)]
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


def _collect_rows(
    group_rows: list, fg: dict | None, show_br: bool
) -> tuple[list[str], list[list[str]]]:
    """Return (headers, data_rows) with all cell values pre-formatted as strings."""
    data_rows: list[list[str]] = []

    if show_br:
        headers = ["Ticker", "Price", "DY%", "Ceiling"]
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
            m = get_br_stock_metrics(ticker, cp)
            dy_str = f"{m['dy_yield']*100:.2f}%" if m["dy_yield"] > 0 else "—"
            data_rows.append([
                name,
                _fmt(cp, sym),
                dy_str,
                _fmt_ceiling(ceiling_val, cp, sym),
            ])
    else:
        has_fg = fg is not None and any(r["ticker"].upper() == "BTC-USD" for r in group_rows)
        headers = ["Ticker", "Price", "H (30d)", "L (30d)"]
        if has_fg:
            headers.append("F&G")
        headers.append("Ceiling")

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
                cells = [name, "—", "—", "—"]
                if has_fg:
                    cells.append("—")
                cells.append("—")
                data_rows.append(cells)
                continue
            cp = market["current_price"]
            cells = [
                name,
                _fmt(cp, sym),
                _fmt(market["high_30d"], sym),
                _fmt(market["low_30d"],  sym),
            ]
            if has_fg:
                cells.append(
                    f"{fg['value']} ({fg['classification']})"
                    if ticker.upper() == "BTC-USD" else "—"
                )
            cells.append(_fmt_ceiling(ceiling_val, cp, sym))
            data_rows.append(cells)

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


def _build_section(title: str, rows: list, fg: dict | None) -> list[str]:
    groups = _group_by_subcategory(rows)
    if not (len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)):
        groups = [(None, rows)]

    messages: list[str] = []
    heading_emitted = False

    def _block(tbl: str, lbl: str | None, with_cat: bool) -> str:
        parts = [f"## {title}"] if with_cat else []
        if lbl:
            parts.append(f"- **{lbl}**")
        parts.append(f"```\n{tbl}\n```")
        return "\n".join(parts)

    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None
        show_br = key == "br-stocks"
        headers, data_rows = _collect_rows(group_rows, fg, show_br)
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
    msg = f"## Buy Opportunities\n```\n{table_str}\n```"
    return [msg] if len(msg) <= _MSG_LIMIT else [msg[:_MSG_LIMIT]]


def build_summary(user_id: int, discord_mention: str) -> list[str]:
    tickers = list_tickers(user_id)
    if not tickers:
        return [f"{discord_mention} You have no tickers configured. Use `!add <TICKER>` to get started."]

    tickers = _backfill_subcategories(user_id, tickers)
    wallet    = [row for row in tickers if row["category"] == "wallet"]
    watchlist = [row for row in tickers if row["category"] == "watchlist"]
    has_btc   = any(row["ticker"].upper() == "BTC-USD" for row in tickers)

    fg = get_fear_greed_index() if has_btc else None

    sections: list[str] = []
    if wallet:
        sections.extend(_build_section("Wallet", wallet, fg))
    if watchlist:
        sections.extend(_build_section("Watchlist", watchlist, fg))

    sections[0] = f"{discord_mention} Your summary:\n{sections[0]}"
    sections.extend(_build_opportunities(tickers))
    return sections


class SummaryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="summary")
    async def summary(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        async with ctx.typing():
            messages = build_summary(user["id"], ctx.author.mention)
        for msg in messages:
            await ctx.send(msg)
        logger.info("Summary sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummaryCog(bot))
