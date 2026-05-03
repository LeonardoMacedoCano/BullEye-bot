import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_alert, ticker_exists
from bot.services.market import normalize_ticker

logger = logging.getLogger(__name__)


class AlertsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="alert")
    async def alert(self, ctx: commands.Context, ticker: str, price: float) -> None:
        ticker = normalize_ticker(ticker)
        user = get_or_create_user(str(ctx.author.id))

        if not ticker_exists(user["id"], ticker):
            await ctx.send(
                f"{ctx.author.mention} Ticker `{ticker}` is not in your list. "
                f"Add it first with `!add {ticker}`."
            )
            return

        add_alert(user["id"], ticker, price)
        await ctx.send(
            f"{ctx.author.mention} Alert set: `{ticker}` <= **${price:.2f}**. "
            f"You will be notified once when this condition is met."
        )
        logger.info("User %s set alert: %s <= %.2f", ctx.author.id, ticker, price)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AlertsCog(bot))
