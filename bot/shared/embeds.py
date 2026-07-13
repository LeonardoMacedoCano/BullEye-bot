from __future__ import annotations

import discord

from bot.shared.formatting import strip_ansi

EMBED_COLOR = discord.Color.from_rgb(47, 128, 237)
COLOR_UP = discord.Color.from_rgb(0, 188, 94)
COLOR_DOWN = discord.Color.from_rgb(220, 50, 60)

_FIELD_LIMIT = 900


def wrap_table_field(table_str: str, lang: str = "ansi") -> str:
    """Wrap a rendered table in a code block, truncating rows to fit an embed field."""
    value = f"```{lang}\n{table_str}\n```"
    if len(strip_ansi(value)) <= _FIELD_LIMIT:
        return value
    lines = table_str.split("\n")
    header = "\n".join(lines[:2])
    data_lines = lines[2:]
    kept: list[str] = []
    for line in data_lines:
        candidate = f"```{lang}\n{header}\n" + "\n".join(kept + [line, "… +99 more"]) + "\n```"
        if len(strip_ansi(candidate)) > _FIELD_LIMIT:
            break
        kept.append(line)
    truncated = len(data_lines) - len(kept)
    body = "\n".join(kept)
    if truncated:
        body += f"\n… +{truncated} more"
    return f"```{lang}\n{header}\n{body}\n```"
