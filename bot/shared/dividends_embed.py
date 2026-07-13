from __future__ import annotations

import datetime
import discord

from bot.shared.embeds import EMBED_COLOR


def dividends_field_value(dividends: list) -> str:
    name_w = max((len(d["name"]) for d in dividends), default=6)
    indent = " " * (name_w + 2)
    lines: list[str] = []
    for d in dividends:
        lines.append(f"{d['name']:<{name_w}}  {d['ex_date']} → {d['pay_date']}")
        amt = d["amount"]
        amt_colored = f"\x1b[2;32m{amt}\x1b[0m" if amt != "—" else amt
        lines.append(f"{indent}{amt_colored}  {d['type']}")
    return "```ansi\n" + "\n".join(lines) + "\n```"


def build_dividends_embed(dividends: list) -> discord.Embed | None:
    if not dividends:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    embed = discord.Embed(title="📅 Upcoming Dividends", color=EMBED_COLOR, timestamp=now)
    embed.add_field(name="Next 60 days", value=dividends_field_value(dividends), inline=False)
    embed.set_footer(text="Amounts via brapi.dev / yfinance · /refreshcache to force refresh")
    return embed
