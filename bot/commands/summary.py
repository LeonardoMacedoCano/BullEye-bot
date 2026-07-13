import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import defer, followup, mention, perf_start, perf_log
from bot.db.repository import get_or_create_user
from bot.application.summary_use_case import build_summary
from bot.shared.summary_embed import build_portfolio_embed, build_intelligence_embed

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
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, build_summary, user["id"], m),
                    timeout=120.0,
                )

                if result.get("empty"):
                    await followup(
                        interaction,
                        f"{m} You have no tickers. Use `/add <TICKER>` to get started.",
                    )
                    return

                embeds: list[discord.Embed] = []

                portfolio_embed = build_portfolio_embed(result)
                if portfolio_embed:
                    embeds.append(portfolio_embed)

                intel_embed = build_intelligence_embed(result)
                if intel_embed:
                    embeds.append(intel_embed)

                if not embeds:
                    await followup(interaction, f"{m} Could not fetch data for your tickers.")
                    return

                await followup(interaction, m, embeds=embeds)
                logger.info("Summary sent to user %s", interaction.user.id)
                perf_log(logger, "summary", t0)
            except asyncio.TimeoutError:
                await followup(interaction, f"{m} ❌ Summary timed out. Please try again.")
            except Exception:
                logger.exception("Error in summary for user %s", interaction.user.id)
                await followup(interaction, f"{m} ❌ Error generating summary. Please try again.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummaryCog(bot))
