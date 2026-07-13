import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers
from bot.application.dividends_use_case import get_dividends_rows
from bot.shared.dividends_embed import build_dividends_embed
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


class DividendsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="dividends", description="Show upcoming dividends in the next 60 days")
    async def dividends(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        tickers = await loop.run_in_executor(None, list_tickers, user["id"])
        if not tickers:
            await followup(
                interaction,
                f"{m} You have no tickers configured. Use `/add <TICKER>` to get started.",
            )
            return

        async with self.bot.heavy_semaphore:
            try:
                rows = await asyncio.wait_for(
                    loop.run_in_executor(None, get_dividends_rows, list(tickers)),
                    timeout=60.0,
                )
            except asyncio.TimeoutError:
                await followup(interaction, f"{m} ❌ Dividends lookup timed out. Please try again.")
                return
            except Exception:
                logger.exception("Error in dividends for user %s", interaction.user.id)
                await followup(interaction, f"{m} ❌ Error fetching dividends. Please try again.")
                return

        embed = build_dividends_embed(rows)
        if not embed:
            await followup(interaction, f"{m} No upcoming dividends in the next 60 days.")
            return

        await followup(interaction, m, embed=embed)
        logger.info("Dividends sent to user %s", interaction.user.id)
        perf_log(logger, "dividends", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DividendsCog(bot))
