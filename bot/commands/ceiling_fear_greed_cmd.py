import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, set_user_fgi_ceiling, clear_user_fgi_ceiling, get_user_fgi_ceiling
from bot.services.fear_greed import get_fear_greed_index
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


class CeilingFearGreedCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="ceiling_fear_greed",
        description="Set, view, or clear your personal Crypto Fear & Greed Index ceiling threshold (1-100)",
    )
    @app_commands.describe(
        value="Ceiling threshold (1-100), or 'clear' to remove. Omit to view current ceiling.",
    )
    async def ceiling_fear_greed(
        self,
        interaction: discord.Interaction,
        value: str | None = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))

        if value is None:
            ceiling = await loop.run_in_executor(None, get_user_fgi_ceiling, user["id"])
            if ceiling is None:
                await followup(interaction, f"{m} No Fear & Greed ceiling set. Use `/ceiling_fear_greed <1-100>` to set one.")
                perf_log(logger, "ceiling_fear_greed", t0)
                return
            fgi = await loop.run_in_executor(None, get_fear_greed_index)
            if fgi:
                delta = fgi["value"] - ceiling
                sign = "+" if delta >= 0 else ""
                status = "above ceiling" if delta >= 0 else "below ceiling"
                await followup(
                    interaction,
                    f"{m} Fear & Greed ceiling: **{ceiling}** — "
                    f"Current: **{fgi['value']}** ({fgi['classification']}) "
                    f"({sign}{delta} {status})",
                )
            else:
                await followup(interaction, f"{m} Fear & Greed ceiling: **{ceiling}** (could not fetch current index)")
            perf_log(logger, "ceiling_fear_greed", t0)
            return

        if value.lower() == "clear":
            await loop.run_in_executor(None, clear_user_fgi_ceiling, user["id"])
            await followup(interaction, f"{m} Fear & Greed ceiling removed.")
            logger.info("User %s cleared Fear & Greed ceiling", interaction.user.id)
            perf_log(logger, "ceiling_fear_greed", t0)
            return

        try:
            ceiling_val = int(value)
            if not (1 <= ceiling_val <= 100):
                raise ValueError
        except ValueError:
            await followup(
                interaction,
                f"{m} Invalid value `{value}`. Use an integer between 1 and 100, or `clear`.",
            )
            return

        await loop.run_in_executor(None, set_user_fgi_ceiling, user["id"], ceiling_val)
        await followup(interaction, f"{m} Fear & Greed ceiling set: index ≤ **{ceiling_val}**.")
        logger.info("User %s set Fear & Greed ceiling to %d", interaction.user.id, ceiling_val)
        perf_log(logger, "ceiling_fear_greed", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CeilingFearGreedCog(bot))
