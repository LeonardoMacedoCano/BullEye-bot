from __future__ import annotations

import discord

from bot.shared.embeds import COLOR_UP, COLOR_DOWN


def build_cache_embed(result: dict) -> discord.Embed:
    color = COLOR_DOWN if result["failed"] > 0 else COLOR_UP
    embed = discord.Embed(title="✅ Cache Refreshed", color=color)
    embed.add_field(name="Tickers updated", value=f"{result['refreshed']}/{result['total']}", inline=True)
    if result["failed"] > 0:
        embed.add_field(name="Failed", value=str(result["failed"]), inline=True)
    embed.set_footer(text="All data is fresh now.")
    return embed
