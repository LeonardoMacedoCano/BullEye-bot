import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import defer, followup, mention, perf_start, perf_log

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="help", description="Show all available BullEyeBot commands")
    async def help_cmd(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        lines = [
            f"{m} **BullEyeBot — Commands**\n",
            "`/add <TICKER> [wallet|watchlist]` — Add a ticker (default: watchlist)",
            "`/remove <TICKER>` — Remove a ticker and its alerts",
            "`/tickers` — Show all your tickers with ceiling, alerts and notes",
            "`/alert <TICKER> <PRICE>` — Alert when price reaches or drops below target (fires once)",
            "`/ceiling <TICKER> <PRICE>` — Set your personal ceiling price for a ticker",
            "`/ceiling <TICKER> clear` — Remove ceiling price",
            "`/ceiling <TICKER>` — Show current ceiling price",
            "`/note <TICKER> <TEXT>` — Set a free-text note for a ticker",
            "`/note <TICKER> clear` — Remove note",
            "`/note <TICKER>` — Show current note",
            "`/schedule <HH:MM>` — Schedule a daily summary DM",
            "`/schedule` — Show your current schedule",
            "`/unschedule` — Cancel your daily summary",
            "`/summary` — Get your current portfolio summary",
            "`/dividends` — Show upcoming dividends (next 60 days) with type, ex-date, pay-date and amount",
            "`/refreshcache` — Clear and re-fetch all data caches (prices, dividends, Fear & Greed)",
            "`/help` — Show this message",
        ]
        await followup(interaction, "\n".join(lines))
        logger.info("Help sent to user %s", interaction.user.id)
        perf_log(logger, "help", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
