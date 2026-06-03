import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_fgi_alert
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


class AlertFearGreedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="alert_fear_greed",
        description="Set a one-time alert when Crypto Fear & Greed Index reaches or drops below target (1-100)",
    )
    @app_commands.describe(
        index="Target index value (1-100) — alert fires once when Fear & Greed Index reaches or drops below this value",
    )
    async def alert_fear_greed(
        self,
        interaction: discord.Interaction,
        index: int,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)

        if not (1 <= index <= 100):
            await followup(
                interaction,
                f"{m} Invalid value `{index}`. Use an integer between 1 and 100.",
            )
            return

        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        await loop.run_in_executor(None, add_fgi_alert, user["id"], index)
        await followup(
            interaction,
            f"{m} Fear & Greed alert set: index ≤ **{index}**. "
            f"You will be notified once when this condition is met.",
        )
        logger.info("User %s set Fear & Greed alert: index <= %d", interaction.user.id, index)
        perf_log(logger, "alert_fear_greed", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AlertFearGreedCog(bot))
