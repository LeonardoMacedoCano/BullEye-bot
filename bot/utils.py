import logging
from typing import Callable

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


async def safe_defer(ctx: commands.Context, ephemeral: bool = False) -> Callable:
    """
    Defers the interaction if needed and returns a send function.
    - Interaction already deferred (by before_invoke hook): returns ctx.send immediately.
    - Defer succeeds now: returns ctx.send.
    - Defer fails (stale interaction): returns a channel_send wrapper.
    Commands never abort — the result is always delivered.
    """
    if ctx.interaction is None:
        return ctx.send

    # Already deferred by the before_invoke hook — nothing to do
    if ctx.interaction.response.is_done():
        return ctx.send

    try:
        await ctx.defer(ephemeral=ephemeral)
        return ctx.send

    except (discord.NotFound, discord.HTTPException) as exc:
        logger.warning(
            "safe_defer: interaction expired (%s) for command '%s' by user %s — falling back to channel",
            getattr(exc, "code", type(exc).__name__),
            ctx.command,
            ctx.author.id if hasattr(ctx, "author") else "?",
        )

        async def _channel_send(content: str = None, **kwargs) -> None:
            kwargs.pop("ephemeral", None)
            await ctx.channel.send(content, **kwargs)

        return _channel_send
