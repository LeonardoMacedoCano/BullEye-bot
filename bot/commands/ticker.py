import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_ticker, remove_ticker, list_tickers, get_ticker_category
from bot.services.market import validate_ticker, normalize_ticker, get_ticker_metadata, SUBCATEGORY_LABELS
from bot.utils import defer, followup, mention, perf_start, perf_log, ticker_autocomplete
from bot.application.ticker_use_case import get_ticker_groups
from bot.shared.tickers_embed import build_tickers_embed

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("wallet", "watchlist")


class TickerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="add", description="Add a ticker to your wallet or watchlist")
    @app_commands.describe(
        ticker="Ticker symbol (e.g. AAPL, BTC, PETR4)",
        category="Which list to add to (default: watchlist)",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="wallet", value="wallet"),
        app_commands.Choice(name="watchlist", value="watchlist"),
    ])
    async def add(
        self,
        interaction: discord.Interaction,
        ticker: str,
        category: app_commands.Choice[str] = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        cat_value = category.value if category is not None else "watchlist"

        original = ticker.upper().strip()
        ticker = normalize_ticker(original)

        def _validate():
            valid = validate_ticker(ticker)
            metadata = get_ticker_metadata(ticker) if valid else {}
            return valid, metadata

        loop = asyncio.get_running_loop()
        try:
            valid, metadata = await loop.run_in_executor(None, _validate)
        except Exception:
            logger.exception("Error validating ticker %s", ticker)
            await followup(interaction, f"{m} ❌ Error validating ticker. Please try again.")
            return

        if not valid:
            await followup(interaction, f"{m} Ticker `{ticker}` not found.")
            return

        subcategory = metadata.get("subcategory")
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        existing = await loop.run_in_executor(None, get_ticker_category, user["id"], ticker)
        if existing == cat_value:
            await followup(interaction, f"{m} `{ticker}` is already in your **{cat_value}**.")
            return
        if existing:
            await followup(
                interaction,
                f"{m} `{ticker}` is already in your **{existing}**. "
                f"Remove it first with `/remove {ticker}`.",
            )
            return

        await loop.run_in_executor(
            None, add_ticker, user["id"], ticker, cat_value,
            subcategory, metadata.get("sector"), metadata.get("industry"),
        )

        sub_label = f" ({SUBCATEGORY_LABELS[subcategory]})" if subcategory in SUBCATEGORY_LABELS else ""
        if ticker != original:
            await followup(
                interaction,
                f"{m} `{original}` interpreted as `{ticker}`. Added to **{cat_value}**{sub_label}.",
            )
        else:
            await followup(interaction, f"{m} Ticker `{ticker}` added to **{cat_value}**{sub_label}.")
        logger.info("User %s added ticker %s to %s (%s)", interaction.user.id, ticker, cat_value, subcategory)
        perf_log(logger, "add", t0)

    @app_commands.command(name="remove", description="Remove a ticker from your list")
    @app_commands.describe(ticker="Ticker symbol to remove")
    async def remove(self, interaction: discord.Interaction, ticker: str) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        original = ticker.upper().strip()
        ticker = normalize_ticker(original)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        count = await loop.run_in_executor(None, remove_ticker, user["id"], ticker)
        if count == 0:
            await followup(interaction, f"{m} Ticker `{ticker}` not found in your list.")
        else:
            await followup(interaction, f"{m} Ticker `{ticker}` removed.")
            logger.info("User %s removed ticker %s", interaction.user.id, ticker)
        perf_log(logger, "remove", t0)

    @remove.autocomplete("ticker")
    async def remove_ticker_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await ticker_autocomplete(interaction, current)

    @app_commands.command(name="tickers", description="Show all your tickers with ceiling, alerts and notes")
    async def tickers_cmd(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        rows = await loop.run_in_executor(None, list_tickers, user["id"])

        if not rows:
            await followup(
                interaction,
                f"{m} Your ticker list is empty. Use `/add <TICKER>` to add one.",
            )
            return

        wallet = [row for row in rows if row["category"] == "wallet"]
        watchlist = [row for row in rows if row["category"] == "watchlist"]

        embed = build_tickers_embed(get_ticker_groups(wallet), get_ticker_groups(watchlist))
        if not embed:
            await followup(interaction, f"{m} Could not fetch data for your tickers.")
            return

        await followup(interaction, m, embed=embed)
        perf_log(logger, "tickers", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TickerCog(bot))
