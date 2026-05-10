import asyncio
import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers
from bot.commands.summary import _build_proventos_radar
from bot.utils import safe_defer

logger = logging.getLogger(__name__)


class DividendsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="dividends")
    async def dividends(self, ctx: commands.Context) -> None:
        send = await safe_defer(ctx)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(ctx.author.id))
        tickers = await loop.run_in_executor(None, list_tickers, user["id"])
        if not tickers:
            await send(
                f"{ctx.author.mention} You have no tickers configured. Use `!add <TICKER>` to get started."
            )
            return

        async with self.bot.heavy_semaphore:
            try:
                messages = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        None, _build_proventos_radar, list(tickers)
                    ),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                await send(f"{ctx.author.mention} ❌ Dividends lookup timed out. Please try again.")
                return
            except Exception:
                logger.exception("Error in dividends for user %s", ctx.author.id)
                await send(f"{ctx.author.mention} ❌ Error fetching dividends. Please try again.")
                return

        if not messages:
            await send(f"{ctx.author.mention} No upcoming dividends in the next 60 days.")
            return

        messages[0] = f"{ctx.author.mention} " + messages[0]
        for msg in messages:
            await send(msg)
        logger.info("Dividends sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DividendsCog(bot))
