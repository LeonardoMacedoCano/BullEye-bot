import asyncio
import logging
import time
from typing import Any

import discord
from discord import app_commands

from bot.shared.context import new_request_id

logger = logging.getLogger(__name__)


async def defer(interaction: discord.Interaction, ephemeral: bool = False) -> bool:
    """Defer the interaction. Returns False on stale interaction (10062) — caller should return immediately."""
    new_request_id()
    try:
        await interaction.response.defer(thinking=True, ephemeral=ephemeral)
        return True
    except discord.NotFound as exc:
        if getattr(exc, "code", None) == 10062:
            logger.warning(
                "defer: stale interaction (10062) for command '%s' by user %s",
                interaction.command.name if interaction.command else "?",
                interaction.user.id,
            )
            return False
        raise
    except discord.HTTPException as exc:
        logger.warning(
            "defer: HTTP error for command '%s' by user %s: %s",
            interaction.command.name if interaction.command else "?",
            interaction.user.id,
            exc,
        )
        return False


async def followup(
    interaction: discord.Interaction,
    content: str,
    **kwargs: Any,
) -> None:
    """Send a followup message. Logs and swallows send failures so multi-message responses don't abort."""
    try:
        await interaction.followup.send(content, **kwargs)
    except (discord.HTTPException, discord.NotFound) as exc:
        logger.warning(
            "followup: failed to send for command '%s': %s",
            interaction.command.name if interaction.command else "?",
            exc,
        )


def mention(interaction: discord.Interaction) -> str:
    """Return the invoking user's mention string."""
    return interaction.user.mention


def perf_start() -> float:
    """Return a high-resolution timestamp for performance tracking."""
    return time.perf_counter()


def perf_log(logger_instance: logging.Logger, command: str, start: float) -> None:
    """Log elapsed time since start."""
    elapsed = time.perf_counter() - start
    logger_instance.info("Command '%s' completed in %.3fs", command, elapsed)


def _display_ticker(ticker: str) -> str:
    if ticker.endswith(".SA"):
        return ticker[:-3]
    return ticker


async def ticker_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    from bot.db.repository import get_or_create_user, list_tickers
    loop = asyncio.get_running_loop()
    try:
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        rows = await loop.run_in_executor(None, list_tickers, user["id"])
    except Exception:
        return []
    upper = current.upper()
    return [
        app_commands.Choice(name=_display_ticker(row["ticker"]), value=row["ticker"])
        for row in rows
        if not upper or upper in row["ticker"]
    ][:25]
