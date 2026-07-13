from __future__ import annotations

import discord

from bot.shared.embeds import EMBED_COLOR, wrap_table_field

_DETAILS_LIMIT = 900


def _join_details(details: list[str]) -> str:
    kept: list[str] = []
    total = 0
    for line in details:
        add = len(line) + 1
        if total + add > _DETAILS_LIMIT:
            remaining = len(details) - len(kept)
            if remaining:
                kept.append(f"… +{remaining} more")
            break
        kept.append(line)
        total += add
    return "\n".join(kept)


def _add_group_fields(embed: discord.Embed, groups: list, prefix: str) -> None:
    for group in groups:
        label = prefix + (f" · {group['label']}" if group["label"] else "")
        embed.add_field(name=label, value=wrap_table_field(group["table_str"], lang=""), inline=False)
        if group["details"]:
            embed.add_field(name="📝 Notes & Sector", value=_join_details(group["details"]), inline=False)


def build_tickers_embed(wallet_groups: list, watchlist_groups: list) -> discord.Embed | None:
    if not wallet_groups and not watchlist_groups:
        return None

    embed = discord.Embed(title="📋 Your Tickers", color=EMBED_COLOR)
    _add_group_fields(embed, wallet_groups, "💼 Wallet")
    _add_group_fields(embed, watchlist_groups, "👀 Watchlist")
    return embed
