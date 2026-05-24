import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import defer, followup, mention, perf_start, perf_log
from bot.db.repository import get_or_create_user
from bot.application.summary_use_case import build_summary

logger = logging.getLogger(__name__)


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
