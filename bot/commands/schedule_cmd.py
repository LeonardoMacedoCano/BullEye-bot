import asyncio
import re
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, set_schedule, get_schedule, deactivate_schedule
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="schedule", description="Schedule a daily portfolio summary DM, or view your current schedule")
    @app_commands.describe(time="Time in HH:MM format (24h, e.g. 08:30). Omit to view your current schedule.")
    async def schedule(
        self,
        interaction: discord.Interaction,
        time: str | None = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))

        if time is None:
            row = await loop.run_in_executor(None, get_schedule, user["id"])
            if row:
                await followup(
                    interaction,
                    f"{m} Your daily summary is scheduled at **{row['time']}**.",
                )
            else:
                await followup(
                    interaction,
                    f"{m} No schedule set. Use `/schedule` with a time like `08:30` to set one.",
                )
            perf_log(logger, "schedule", t0)
            return

        match = _TIME_RE.match(time)
        if not match:
            await followup(
                interaction,
                f"{m} Invalid time format. Use `HH:MM` (e.g. `08:30`).",
            )
            return

        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            await followup(
                interaction,
                f"{m} Invalid time `{time}`. Hour must be 00-23 and minute 00-59.",
            )
            return

        await loop.run_in_executor(None, set_schedule, user["id"], time)
        await followup(interaction, f"{m} Daily summary scheduled at **{time}**.")
        logger.info("User %s set daily schedule at %s", interaction.user.id, time)
        perf_log(logger, "schedule", t0)

    @app_commands.command(name="unschedule", description="Cancel your daily portfolio summary")
    async def unschedule(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        count = await loop.run_in_executor(None, deactivate_schedule, user["id"])
        if count == 0:
            await followup(interaction, f"{m} You have no active schedule to cancel.")
        else:
            await followup(interaction, f"{m} Daily summary cancelled.")
            logger.info("User %s cancelled their daily schedule", interaction.user.id)
        perf_log(logger, "unschedule", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScheduleCog(bot))
