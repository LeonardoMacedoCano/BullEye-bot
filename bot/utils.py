import discord
from discord.ext import commands


async def safe_defer(ctx: commands.Context) -> bool:
    """Tenta defer. Retorna False se a interação já expirou (10062)."""
    try:
        await ctx.defer()
        return True
    except discord.NotFound:
        return False
