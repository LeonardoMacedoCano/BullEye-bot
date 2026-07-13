from __future__ import annotations

import discord

from bot.shared.embeds import EMBED_COLOR, wrap_table_field


def build_tickers_embed(wallet_groups: list, watchlist_groups: list) -> discord.Embed | None:
    if not wallet_groups and not watchlist_groups:
        return None

    embed = discord.Embed(title="📋 Your Tickers", color=EMBED_COLOR)

    for group in wallet_groups:
        label = "💼 Wallet" + (f" · {group['label']}" if group["label"] else "")
        embed.add_field(name=label, value=wrap_table_field(group["table_str"], lang=""), inline=False)

    for group in watchlist_groups:
        label = "👀 Watchlist" + (f" · {group['label']}" if group["label"] else "")
        embed.add_field(name=label, value=wrap_table_field(group["table_str"], lang=""), inline=False)

    return embed
