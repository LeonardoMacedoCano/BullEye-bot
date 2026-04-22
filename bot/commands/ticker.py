import logging
import discord
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_ticker, remove_ticker, list_tickers
from bot.services.market import validate_ticker

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("wallet", "watchlist")


class TickerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="add")
    async def add(self, ctx: commands.Context, ticker: str, category: str = "watchlist") -> None:
        if category not in VALID_CATEGORIES:
            await ctx.send(
                f"{ctx.author.mention} Invalid category `{category}`. Use `wallet` or `watchlist`."
            )
            return

        ticker = ticker.upper()
        async with ctx.typing():
            valid = validate_ticker(ticker)

        if not valid:
            await ctx.send(
                f"{ctx.author.mention} Ticker `{ticker}` not found. Please use a valid ticker symbol (e.g. AAPL, BTC-USD)."
            )
            return

        user = get_or_create_user(str(ctx.author.id))
        add_ticker(user["id"], ticker, category)
        await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` added to **{category}**.")
        logger.info("User %s added ticker %s to %s", ctx.author.id, ticker, category)

    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, ticker: str) -> None:
        ticker = ticker.upper()
        user = get_or_create_user(str(ctx.author.id))
        count = remove_ticker(user["id"], ticker)
        if count == 0:
            await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` not found in your list.")
        else:
            await ctx.send(f"{ctx.author.mention} Ticker `{ticker}` removed.")
            logger.info("User %s removed ticker %s", ctx.author.id, ticker)

    @commands.command(name="list")
    async def list_tickers_cmd(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        tickers = list_tickers(user["id"])

        if not tickers:
            await ctx.send(
                f"{ctx.author.mention} Your ticker list is empty. Use `!add <TICKER>` to add one."
            )
            return

        wallet = [row["ticker"] for row in tickers if row["category"] == "wallet"]
        watchlist = [row["ticker"] for row in tickers if row["category"] == "watchlist"]

        lines = [f"{ctx.author.mention} Your tickers:\n"]
        if wallet:
            lines.append(f"**Wallet:** {', '.join(wallet)}")
        if watchlist:
            lines.append(f"**Watchlist:** {', '.join(watchlist)}")

        await ctx.send("\n".join(lines))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TickerCog(bot))
