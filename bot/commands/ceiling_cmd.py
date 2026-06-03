import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, get_ticker_category, get_ticker_row, set_user_ceiling, clear_user_ceiling
from bot.services.market import normalize_ticker, get_ticker_data
from bot.utils import defer, followup, mention, perf_start, perf_log, ticker_autocomplete
from bot.shared.formatting import currency

logger = logging.getLogger(__name__)


class CeilingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="ceiling", description="Set, view, or clear your personal ceiling price for a ticker")
    @app_commands.describe(
        ticker="Ticker symbol",
        value="New ceiling price, or 'clear' to remove. Omit to view current ceiling.",
    )
    async def ceiling(
        self,
        interaction: discord.Interaction,
        ticker: str,
        value: str | None = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        original = ticker.upper().strip()
        ticker = normalize_ticker(original)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))

        if not await loop.run_in_executor(None, get_ticker_category, user["id"], ticker):
            await followup(
                interaction,
                f"{m} `{ticker}` is not in your list. Add it first with `/add`.",
            )
            return

        sym = currency(ticker)

        if value is None:
            row = await loop.run_in_executor(None, get_ticker_row, user["id"], ticker)
            user_ceiling = row["user_ceiling"] if row else None
            if user_ceiling is None:
                await followup(interaction, f"{m} No ceiling set for `{ticker}`.")
                return
            try:
                data = await loop.run_in_executor(None, get_ticker_data, ticker)
            except Exception:
                logger.exception("Error fetching data for %s", ticker)
                await followup(interaction, f"{m} ❌ Error fetching price. Please try again.")
                return
            if data:
                price = data["current_price"]
                margin = (user_ceiling - price) / price * 100
                sign = "+" if margin >= 0 else ""
                status = "below ceiling" if margin >= 0 else "above ceiling"
                await followup(
                    interaction,
                    f"{m} `{ticker}` ceiling: {sym}{user_ceiling:,.2f} — "
                    f"Current: {sym}{price:,.2f} ({sign}{margin:.1f}% {status})",
                )
            else:
                await followup(interaction, f"{m} `{ticker}` ceiling: {sym}{user_ceiling:,.2f}")
            perf_log(logger, "ceiling", t0)
            return

        if value.lower() == "clear":
            await loop.run_in_executor(None, clear_user_ceiling, user["id"], ticker)
            await followup(interaction, f"{m} Ceiling removed for `{ticker}`.")
            logger.info("User %s cleared ceiling for %s", interaction.user.id, ticker)
            perf_log(logger, "ceiling", t0)
            return

        try:
            ceiling_val = float(value.replace(",", "."))
            if ceiling_val <= 0:
                raise ValueError
        except ValueError:
            await followup(
                interaction,
                f"{m} Invalid price `{value}`. Use a positive number or `clear`.",
            )
            return

        await loop.run_in_executor(None, set_user_ceiling, user["id"], ticker, ceiling_val)
        await followup(interaction, f"{m} Ceiling set: `{ticker}` ≤ {sym}{ceiling_val:,.2f}.")
        logger.info("User %s set ceiling for %s to %.2f", interaction.user.id, ticker, ceiling_val)
        perf_log(logger, "ceiling", t0)

    @ceiling.autocomplete("ticker")
    async def ceiling_ticker_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await ticker_autocomplete(interaction, current)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CeilingCog(bot))
