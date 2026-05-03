import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers
from bot.commands.summary import _build_dividends_radar

logger = logging.getLogger(__name__)


class DividendsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="dividends")
    async def dividends(self, ctx: commands.Context) -> None:
        await ctx.defer()
        user = get_or_create_user(str(ctx.author.id))
        async with ctx.typing():
            tickers = list_tickers(user["id"])
            if not tickers:
                await ctx.send(
                    f"{ctx.author.mention} You have no tickers configured. Use `!add <TICKER>` to get started."
                )
                return
            messages = _build_dividends_radar(list(tickers))

        if not messages:
            await ctx.send(f"{ctx.author.mention} No upcoming dividends in the next 60 days.")
            return

        messages[0] = f"{ctx.author.mention} " + messages[0]
        for msg in messages:
            await ctx.send(msg)
        logger.info("Dividends sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DividendsCog(bot))
