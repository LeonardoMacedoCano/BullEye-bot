import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


async def safe_defer(ctx: commands.Context) -> bool:
    try:
        await ctx.defer()
        return True
    except discord.NotFound:
        logger.warning(
            "safe_defer: interaction expired (10062) for command '%s' by user %s",
            ctx.command,
            ctx.author.id if hasattr(ctx, "author") else "?",
        )
        return False
