import logging
import discord
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers, update_ticker_subcategory
from bot.services.market import get_ticker_data, get_ticker_subcategory, SUBCATEGORY_ORDER, SUBCATEGORY_LABELS
from bot.services.fear_greed import get_fear_greed_index

logger = logging.getLogger(__name__)

_COL_TICKER = 10
_COL_PRICE = 13
_COL_HIGH = 13
_COL_LOW = 13
_COL_FG = 18


def _display_name(ticker: str) -> str:
    if ticker.upper() == "BTC-USD":
        return "BTC"
    return ticker[:-3] if ticker.upper().endswith(".SA") else ticker


def _currency(ticker: str) -> str:
    return "R$" if ticker.upper().endswith(".SA") else "$"


def _fmt(value: float, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def _render_rows(rows: list, fg: dict | None) -> str:
    has_fg_col = fg is not None and any(r["ticker"].upper() == "BTC-USD" for r in rows)
    base_width = _COL_TICKER + _COL_PRICE + _COL_HIGH + _COL_LOW
    separator = "─" * (base_width + (_COL_FG if has_fg_col else 0) + 3)
    header = (
        f"{'Ticker':<{_COL_TICKER}}"
        f"{'Price':<{_COL_PRICE}}"
        f"{'H (30d)':<{_COL_HIGH}}"
        f"{'L (30d)':<{_COL_LOW}}"
    )
    if has_fg_col:
        header += f"{'F&G':<{_COL_FG}}"
    lines = [header, separator]
    for row in rows:
        ticker = row["ticker"]
        data = get_ticker_data(ticker)
        name = _display_name(ticker)
        if not data:
            lines.append(f"{name:<{_COL_TICKER}}data unavailable")
            continue
        sym = _currency(ticker)
        price = _fmt(data["current_price"], sym)
        high = _fmt(data["high_30d"], sym)
        low = _fmt(data["low_30d"], sym)
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


def _build_section(title: str, rows: list, fg: dict | None) -> str:
    groups = _group_by_subcategory(rows)
    use_groups = len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)

    if use_groups:
        parts = []
        for key, group_rows in groups:
            label = SUBCATEGORY_LABELS.get(key, key) if key else None
            block = _render_rows(group_rows, fg)
            parts.append(f"{label}\n{block}" if label else block)
        inner = "\n\n".join(parts)
    else:
        inner = _render_rows(rows, fg)

    return f"{title}\n```\n{inner}\n```"


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


def build_summary(user_id: int, discord_mention: str) -> str:
    tickers = list_tickers(user_id)
    if not tickers:
        return f"{discord_mention} You have no tickers configured. Use `!add <TICKER>` to get started."

    tickers = _backfill_subcategories(user_id, tickers)
    wallet = [row for row in tickers if row["category"] == "wallet"]
    watchlist = [row for row in tickers if row["category"] == "watchlist"]
    has_btc = any(row["ticker"].upper() == "BTC-USD" for row in tickers)

    fg = get_fear_greed_index() if has_btc else None

    parts = [f"{discord_mention} Your summary:"]
    if wallet:
        parts.append(_build_section("Wallet", wallet, fg))
    if watchlist:
        parts.append(_build_section("Watchlist", watchlist, fg))

    return "\n".join(parts)


class SummaryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        async with ctx.typing():
            message = build_summary(user["id"], ctx.author.mention)
        await ctx.send(message)
        logger.info("Resume sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummaryCog(bot))
