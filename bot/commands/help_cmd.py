import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import defer, followup, mention, perf_start, perf_log
from bot.shared.help_embed import build_help_embed

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
        await followup(interaction, m, embed=build_help_embed())
        logger.info("Help sent to user %s", interaction.user.id)
        perf_log(logger, "help", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
