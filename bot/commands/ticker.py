import asyncio
import logging
from typing import Literal
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_ticker, remove_ticker, list_tickers, get_ticker_category
from bot.services.market import validate_ticker, normalize_ticker, get_ticker_subcategory, SUBCATEGORY_LABELS, SUBCATEGORY_ORDER
from bot.utils import safe_defer

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("wallet", "watchlist")


def _group_tickers(rows) -> list[tuple[str | None, list[str]]]:
    groups: dict[str | None, list[str]] = {}
    for row in rows:
        try:
            key = row["subcategory"]
        except (IndexError, KeyError):
            key = None
        if key not in groups:
            groups[key] = []
        groups[key].append(row["ticker"])

    ordered = []
    for key in SUBCATEGORY_ORDER:
        if key in groups:
            ordered.append((SUBCATEGORY_LABELS.get(key, key), groups[key]))
    for key, vals in groups.items():
        if key is not None and key not in SUBCATEGORY_ORDER:
            ordered.append((key, vals))
    if None in groups:
        ordered.append((None, groups[None]))
    return ordered


class TickerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="add")
    async def add(self, ctx: commands.Context, ticker: str, category: Literal["wallet", "watchlist"] = "watchlist") -> None:
        if not await safe_defer(ctx):
            return
        if category not in VALID_CATEGORIES:
            await ctx.send(
                f"{ctx.author.mention} Invalid category `{category}`. Use `wallet` or `watchlist`."
            )
            return

        original = ticker.upper().strip()
        ticker = normalize_ticker(original)

        def _validate():
            valid = validate_ticker(ticker)
            subcategory = get_ticker_subcategory(ticker) if valid else None
            return valid, subcategory

        try:
            loop = asyncio.get_event_loop()
            valid, subcategory = await loop.run_in_executor(None, _validate)
        except Exception:
            logger.exception("Error validating ticker %s", ticker)
            await ctx.send(f"{ctx.author.mention} ❌ Erro ao validar o ticker. Tente novamente.")
            return

        if not valid:
            await ctx.send(
                f"{ctx.author.mention} Ticker `{ticker}` not found."
            )
            return

        user = get_or_create_user(str(ctx.author.id))
        existing = get_ticker_category(user["id"], ticker)
        if existing == category:
            await ctx.send(f"{ctx.author.mention} `{ticker}` is already in your **{category}**.")
            return
        if existing:
            await ctx.send(
                f"{ctx.author.mention} `{ticker}` is already in your **{existing}**. "
                f"Remove it first with `!remove {ticker}`."
            )
            return

        add_ticker(user["id"], ticker, category, subcategory)

        sub_label = f" ({SUBCATEGORY_LABELS[subcategory]})" if subcategory in SUBCATEGORY_LABELS else ""
        if ticker != original:
            await ctx.send(
                f"{ctx.author.mention} `{original}` interpreted as `{ticker}`. Added to **{category}**{sub_label}."
            )
        else:
            await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` added to **{category}**{sub_label}.")
        logger.info("User %s added ticker %s to %s (%s)", ctx.author.id, ticker, category, subcategory)

    @commands.hybrid_command(name="remove")
    async def remove(self, ctx: commands.Context, ticker: str) -> None:
        original = ticker.upper().strip()
        ticker = normalize_ticker(original)
        user = get_or_create_user(str(ctx.author.id))
        count = remove_ticker(user["id"], ticker)
        if count == 0:
            await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` not found in your list.")
        else:
            await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` removed.")
            logger.info("User %s removed ticker %s", ctx.author.id, ticker)

    @commands.hybrid_command(name="list")
    async def list_tickers_cmd(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        tickers = list_tickers(user["id"])

        if not tickers:
            await ctx.send(
                f"{ctx.author.mention} Your ticker list is empty. Use `!add <TICKER>` to add one."
            )
            return

        wallet = [row for row in tickers if row["category"] == "wallet"]
        watchlist = [row for row in tickers if row["category"] == "watchlist"]

        lines = [f"{ctx.author.mention} Your tickers:\n"]
        for cat_label, cat_rows in (("Wallet", wallet), ("Watchlist", watchlist)):
            if not cat_rows:
                continue
            groups = _group_tickers(cat_rows)
            use_groups = len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)
            if use_groups:
                lines.append(f"**{cat_label}:**")
                for label, names in groups:
                    prefix = f"  *{label}:* " if label else "  "
                    lines.append(f"{prefix}{', '.join(names)}")
            else:
                names = [row["ticker"] for row in cat_rows]
                lines.append(f"**{cat_label}:** {', '.join(names)}")

        await ctx.send("\n".join(lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TickerCog(bot))
