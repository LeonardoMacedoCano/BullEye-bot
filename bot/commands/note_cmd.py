import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, get_ticker_category, get_ticker_row, set_user_note, clear_user_note
from bot.services.market import normalize_ticker
from bot.utils import defer, followup, mention, perf_start, perf_log, ticker_autocomplete

logger = logging.getLogger(__name__)


class NoteCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="note", description="Set or view a note for a ticker")
    @app_commands.describe(
        ticker="Ticker symbol",
        text="Your note text, or 'clear' to remove. Omit to view the current note.",
    )
    async def note(
        self,
        interaction: discord.Interaction,
        ticker: str,
        text: app_commands.Range[str, 1, 80] | None = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        ticker = normalize_ticker(ticker.upper().strip())
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))

        if not await loop.run_in_executor(None, get_ticker_category, user["id"], ticker):
            await followup(
                interaction,
                f"{m} `{ticker}` is not in your list. Add it first with `/add`.",
            )
            return

        if text is None:
            row = await loop.run_in_executor(None, get_ticker_row, user["id"], ticker)
            current = row["note"] if row else None
            if current:
                await followup(interaction, f"{m} Note for `{ticker}`: {current}")
            else:
                await followup(interaction, f"{m} No note set for `{ticker}`.")
            perf_log(logger, "note", t0)
            return

        if text.lower() == "clear":
            await loop.run_in_executor(None, clear_user_note, user["id"], ticker)
            await followup(interaction, f"{m} Note removed for `{ticker}`.")
            logger.info("User %s cleared note for %s", interaction.user.id, ticker)
            perf_log(logger, "note", t0)
            return

        await loop.run_in_executor(None, set_user_note, user["id"], ticker, text)
        await followup(interaction, f"{m} Note set for `{ticker}`: {text}")
        logger.info("User %s set note for %s", interaction.user.id, ticker)
        perf_log(logger, "note", t0)

    @note.autocomplete("ticker")
    async def note_ticker_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await ticker_autocomplete(interaction, current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NoteCog(bot))
