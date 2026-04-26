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

_COL_TICKER = 10
_COL_PRICE  = 13
_COL_HIGH   = 13
_COL_LOW    = 13
_COL_FG     = 18
_COL_DY     = 8
_COL_TETO   = 15  # "R$123.45 +999%" = 14 chars + 1 padding


def _display_name(ticker: str) -> str:
    if ticker.upper() == "BTC-USD":
        return "BTC"
    return ticker[:-3] if ticker.upper().endswith(".SA") else ticker


def _currency(ticker: str) -> str:
    return "R$" if ticker.upper().endswith(".SA") else "$"


def _fmt(value: float, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def _fmt_ceiling(ceiling: float | None, current_price: float) -> str:
    if ceiling is None:
        return "—"
    m = (ceiling - current_price) / current_price * 100
    sign = "+" if m >= 0 else ""
    return f"R${ceiling:,.2f} {sign}{m:.0f}%"


def _render_rows(rows: list, fg: dict | None, show_br_metrics: bool = False) -> str:
    if show_br_metrics:
        sep_width = _COL_TICKER + _COL_PRICE + _COL_DY + _COL_TETO * 4 + 3
        header = (
            f"{'Ticker':<{_COL_TICKER}}"
            f"{'Price':<{_COL_PRICE}}"
            f"{'DY%':<{_COL_DY}}"
            f"{'Bazin':<{_COL_TETO}}"
            f"{'Graham':<{_COL_TETO}}"
            f"{'P/E×15':<{_COL_TETO}}"
            f"{'P/B×1.5':<{_COL_TETO}}"
        )
    else:
        has_fg_col = fg is not None and any(r["ticker"].upper() == "BTC-USD" for r in rows)
        sep_width = _COL_TICKER + _COL_PRICE + _COL_HIGH + _COL_LOW + (_COL_FG if has_fg_col else 0) + 3
        header = (
            f"{'Ticker':<{_COL_TICKER}}"
            f"{'Price':<{_COL_PRICE}}"
            f"{'H (30d)':<{_COL_HIGH}}"
            f"{'L (30d)':<{_COL_LOW}}"
        )
        if has_fg_col:
            header += f"{'F&G':<{_COL_FG}}"

    lines = [header, "─" * sep_width]

    for row in rows:
        ticker = row["ticker"]
        data = get_ticker_data(ticker)
        name = _display_name(ticker)
        if not data:
            lines.append(f"{name:<{_COL_TICKER}}data unavailable")
            continue

        sym   = _currency(ticker)
        price = _fmt(data["current_price"], sym)

        if show_br_metrics:
            m = get_br_stock_metrics(ticker, data["current_price"])
            dy_str = f"{m['dy_yield']*100:.2f}%" if m["dy_yield"] > 0 else "—"
            cp = data["current_price"]
            line = (
                f"{name:<{_COL_TICKER}}"
                f"{price:<{_COL_PRICE}}"
                f"{dy_str:<{_COL_DY}}"
                f"{_fmt_ceiling(m['bazin'],  cp):<{_COL_TETO}}"
                f"{_fmt_ceiling(m['graham'], cp):<{_COL_TETO}}"
                f"{_fmt_ceiling(m['pe15'],   cp):<{_COL_TETO}}"
                f"{_fmt_ceiling(m['pb15'],   cp):<{_COL_TETO}}"
            )
        else:
            high = _fmt(data["high_30d"], sym)
            low  = _fmt(data["low_30d"], sym)
            line = (
                f"{name:<{_COL_TICKER}}"
                f"{price:<{_COL_PRICE}}"
                f"{high:<{_COL_HIGH}}"
                f"{low:<{_COL_LOW}}"
            )
            if has_fg_col:
                fg_cell = f"{fg['value']} ({fg['classification']})" if ticker.upper() == "BTC-USD" else ""
                line += f"{fg_cell:<{_COL_FG}}"

        lines.append(line)

    return "\n".join(lines)


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


_MSG_LIMIT = 1900


def _build_section(title: str, rows: list, fg: dict | None) -> list[str]:
    groups = _group_by_subcategory(rows)
    if not (len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)):
        groups = [(None, rows)]

    def _wrap(parts: list[str]) -> str:
        return f"{title}\n```\n" + "\n\n".join(parts) + "\n```"

    # Render each group block; if a block alone exceeds the limit, split its rows
    raw_blocks: list[str] = []
    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None
        show_br = key == "br-stocks"
        block = _render_rows(group_rows, fg, show_br_metrics=show_br)
        entry = f"{label}\n{block}" if label else block
        if len(_wrap([entry])) <= _MSG_LIMIT:
            raw_blocks.append(entry)
        else:
            # Split rows in batches, repeating the table header each time
            header_lines = "\n".join(block.split("\n")[:2])  # column names + separator
            batch: list[str] = []
            for data_line in block.split("\n")[2:]:
                candidate = header_lines + "\n" + "\n".join(batch + [data_line])
                entry_candidate = f"{label}\n{candidate}" if label else candidate
                if len(_wrap([entry_candidate])) > _MSG_LIMIT and batch:
                    finished = header_lines + "\n" + "\n".join(batch)
                    raw_blocks.append(f"{label}\n{finished}" if label else finished)
                    batch = [data_line]
                else:
                    batch.append(data_line)
            if batch:
                finished = header_lines + "\n" + "\n".join(batch)
                raw_blocks.append(f"{label}\n{finished}" if label else finished)

    # Pack blocks greedily into messages
    messages: list[str] = []
    current: list[str] = []
    for block in raw_blocks:
        candidate = current + [block]
        if len(_wrap(candidate)) > _MSG_LIMIT and current:
            messages.append(_wrap(current))
            current = [block]
        else:
            current = candidate
    if current:
        messages.append(_wrap(current))

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


_COL_MARGIN = 8
_COL_IN = 10


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

    sep_width = _COL_TICKER + _COL_PRICE + _COL_TETO + _COL_MARGIN + _COL_IN + 3
    header = (
        f"{'Ticker':<{_COL_TICKER}}"
        f"{'Price':<{_COL_PRICE}}"
        f"{'Ceiling':<{_COL_TETO}}"
        f"{'Margin':<{_COL_MARGIN}}"
        f"{'In':<{_COL_IN}}"
    )
    lines = [header, "─" * sep_width]

    for opp in opportunities:
        ticker = opp["ticker"]
        sym = _currency(ticker)
        name = _display_name(ticker)
        margin_str = f"+{opp['margin_pct']:.1f}%"
        lines.append(
            f"{name:<{_COL_TICKER}}"
            f"{_fmt(opp['current_price'], sym):<{_COL_PRICE}}"
            f"{_fmt(opp['user_ceiling'], sym):<{_COL_TETO}}"
            f"{margin_str:<{_COL_MARGIN}}"
            f"{opp['category']:<{_COL_IN}}"
        )

    inner = "\n".join(lines)
    msg = f"Buy Opportunities\n```\n{inner}\n```"
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
