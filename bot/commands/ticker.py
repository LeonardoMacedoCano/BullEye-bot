import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_ticker, remove_ticker, list_tickers, get_ticker_category
from bot.services.market import validate_ticker, normalize_ticker, get_ticker_subcategory, SUBCATEGORY_LABELS, SUBCATEGORY_ORDER
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("wallet", "watchlist")


def _group_tickers(rows) -> list[tuple[str | None, list[str]]]:
    groups: dict[str | None, list[str]] = {}
    for row in rows:
        try:
            key = row["subcategory"]
        except (IndexError, KeyError):
            key = None
        if key not in groups:
            groups[key] = []
        groups[key].append(row["ticker"])

    ordered = []
    for key in SUBCATEGORY_ORDER:
        if key in groups:
            ordered.append((SUBCATEGORY_LABELS.get(key, key), groups[key]))
    for key, vals in groups.items():
        if key is not None and key not in SUBCATEGORY_ORDER:
            ordered.append((key, vals))
    if None in groups:
        ordered.append((None, groups[None]))
    return ordered


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
            subcategory = get_ticker_subcategory(ticker) if valid else None
            return valid, subcategory

        loop = asyncio.get_running_loop()
        try:
            valid, subcategory = await loop.run_in_executor(None, _validate)
        except Exception:
            logger.exception("Error validating ticker %s", ticker)
            await followup(interaction, f"{m} ❌ Error validating ticker. Please try again.")
            return

        if not valid:
            await followup(interaction, f"{m} Ticker `{ticker}` not found.")
            return

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

        await loop.run_in_executor(None, add_ticker, user["id"], ticker, cat_value, subcategory)

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

    @app_commands.command(name="list", description="List all your tickers")
    async def list_tickers_cmd(self, interaction: discord.Interaction) -> None:
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
                f"{m} Your ticker list is empty. Use `/add <TICKER>` to add one.",
            )
            return

        wallet = [row for row in tickers if row["category"] == "wallet"]
        watchlist = [row for row in tickers if row["category"] == "watchlist"]

        lines = [f"{m} Your tickers:\n"]
        for cat_label, cat_rows in (("Wallet", wallet), ("Watchlist", watchlist)):
            if not cat_rows:
                continue
            groups = _group_tickers(cat_rows)
            use_groups = len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)
            if use_groups:
                lines.append(f"**{cat_label}:**")
                for label, names in groups:
                    prefix = f"  *{label}:* " if label else "  "
                    lines.append(f"{prefix}{', '.join(names)}")
            else:
                names = [row["ticker"] for row in cat_rows]
                lines.append(f"**{cat_label}:** {', '.join(names)}")

        await followup(interaction, "\n".join(lines))
        perf_log(logger, "list", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TickerCog(bot))
