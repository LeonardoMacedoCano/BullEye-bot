import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_alert, ticker_exists
from bot.services.market import normalize_ticker
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


class AlertsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="alert", description="Set a price alert for a ticker (fires once when price reaches or drops below target)")
    @app_commands.describe(
        ticker="Ticker symbol (e.g. AAPL, PETR4)",
        price="Target price — alert fires when price reaches or drops below this value",
    )
    async def alert(
        self,
        interaction: discord.Interaction,
        ticker: str,
        price: float,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        ticker = normalize_ticker(ticker)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))

        if not await loop.run_in_executor(None, ticker_exists, user["id"], ticker):
            await followup(
                interaction,
                f"{m} Ticker `{ticker}` is not in your list. "
                f"Add it first with `/add {ticker}`.",
            )
            return

        await loop.run_in_executor(None, add_alert, user["id"], ticker, price)
        await followup(
            interaction,
            f"{m} Alert set: `{ticker}` <= **${price:.2f}**. "
            f"You will be notified once when this condition is met.",
        )
        logger.info("User %s set alert: %s <= %.2f", interaction.user.id, ticker, price)
        perf_log(logger, "alert", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AlertsCog(bot))
