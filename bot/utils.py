import logging
import time
from typing import Any

import discord

logger = logging.getLogger(__name__)


async def defer(interaction: discord.Interaction, ephemeral: bool = False) -> bool:
    """Defer the interaction. Returns False on stale interaction (10062) — caller should return immediately."""
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
