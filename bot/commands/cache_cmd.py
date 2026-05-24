import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers, clear_price_cache_db, clear_proventos_db
from bot.services.market import clear_price_cache, get_ticker_data
from bot.application.market_cache import get_br_stock_metrics, get_dividend_info
from bot.services.fear_greed import clear_fear_greed_cache, get_fear_greed_index
from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


def _refresh_all(user_id: int) -> dict:
    from bot.db.repository import list_tickers as _list

    clear_price_cache()
    clear_price_cache_db()
    clear_proventos_db()
    clear_fear_greed_cache()

    tickers = list(_list(user_id))
    refreshed = 0
    failed = 0

    for row in tickers:
        ticker = row["ticker"]
        try:
            data = get_ticker_data(ticker)
            if data is None:
                failed += 1
                continue
            if ticker.upper().endswith(".SA"):
                get_br_stock_metrics(ticker, data["current_price"])
            else:
                get_dividend_info(ticker)
            refreshed += 1
        except Exception as exc:
            logger.warning("Failed to refresh cache for %s: %s", ticker, exc)
            failed += 1

    get_fear_greed_index()
    return {"total": len(tickers), "refreshed": refreshed, "failed": failed}


class CacheCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="refreshcache", description="Clear and re-fetch all data caches (prices, dividends, Fear & Greed)")
    async def refreshcache(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        try:
            result = await loop.run_in_executor(None, _refresh_all, user["id"])
            lines = [
                f"{m} ✅ Cache refreshed successfully!\n",
                f"- **{result['refreshed']}/{result['total']}** tickers updated",
            ]
            if result["failed"] > 0:
                lines.append(f"- **{result['failed']}** tickers failed (check logs)")
            lines.append("\nAll data is fresh now.")
            await followup(interaction, "\n".join(lines))
        except Exception:
            logger.exception("Error in refreshcache for user %s", interaction.user.id)
            await followup(interaction, f"{m} ❌ Error refreshing cache. Please try again.")
        logger.info("Cache refreshed by user %s", interaction.user.id)
        perf_log(logger, "refreshcache", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CacheCog(bot))
