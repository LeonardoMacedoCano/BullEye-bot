from __future__ import annotations

import discord

from bot.shared.embeds import EMBED_COLOR

_SECTIONS = [
    ("🎯 Tickers", [
        "`/add <TICKER> [wallet|watchlist]` — Add a ticker (default: watchlist)",
        "`/remove <TICKER>` — Remove a ticker and its alerts",
        "`/tickers` — Show all your tickers with ceiling, alerts and notes",
    ]),
    ("🔔 Alerts & Ceilings", [
        "`/alert <TICKER> <PRICE>` — Alert when price reaches or drops below target (fires once)",
        "`/ceiling <TICKER> <PRICE>` — Set your personal ceiling price for a ticker",
        "`/ceiling <TICKER> clear` — Remove ceiling price",
        "`/ceiling <TICKER>` — Show current ceiling price",
        "`/ceiling_fear_greed <1-100>` — Set your personal Crypto Fear & Greed Index ceiling threshold",
        "`/ceiling_fear_greed clear` — Remove Fear & Greed ceiling",
        "`/ceiling_fear_greed` — Show current Fear & Greed Index vs your ceiling",
        "`/alert_fear_greed <1-100>` — Alert when Fear & Greed Index reaches or drops below target (fires once)",
    ]),
    ("📝 Notes", [
        "`/note <TICKER> <TEXT>` — Set a free-text note for a ticker",
        "`/note <TICKER> clear` — Remove note",
        "`/note <TICKER>` — Show current note",
    ]),
    ("📊 Summary & Schedule", [
        "`/summary` — Get your current portfolio summary",
        "`/dividends` — Show upcoming dividends (next 60 days) with type, ex-date, pay-date and amount",
        "`/schedule <HH:MM>` — Schedule a daily summary DM",
        "`/schedule` — Show your current schedule",
        "`/unschedule` — Cancel your daily summary",
    ]),
    ("⚙️ Admin", [
        "`/refreshcache` — Clear and re-fetch all data caches (prices, dividends, Fear & Greed)",
        "`/help` — Show this message",
    ]),
]


def build_help_embed() -> discord.Embed:
    embed = discord.Embed(title="BullEyeBot — Commands", color=EMBED_COLOR)
    for name, lines in _SECTIONS:
        embed.add_field(name=name, value="\n".join(lines), inline=False)
    return embed
