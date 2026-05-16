import asyncio
import logging
import os
import sys

import discord
import discord.app_commands as app_commands
from discord.ext import commands
from dotenv import load_dotenv

from bot.db.database import init_db
from bot.scheduler import scheduler_loop

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    logger.error("DISCORD_TOKEN environment variable is not set. Exiting.")
    sys.exit(1)

COGS = [
    "bot.commands.ticker",
    "bot.commands.alerts",
    "bot.commands.schedule_cmd",
    "bot.commands.summary",
    "bot.commands.ceiling_cmd",
    "bot.commands.dividends_cmd",
    "bot.commands.cache_cmd",
    "bot.commands.help_cmd",
    "bot.commands.resetdb_cmd",
]

intents = discord.Intents.default()

bot = commands.Bot(command_prefix=[], intents=intents, help_command=None)
bot.heavy_semaphore = asyncio.Semaphore(3)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    cause = error
    while hasattr(cause, "original"):
        cause = cause.original

    if isinstance(cause, discord.NotFound) and getattr(cause, "code", None) == 10062:
        logger.warning(
            "Stale interaction (10062) for command '%s' by user %s",
            interaction.command.name if interaction.command else "?",
            interaction.user.id,
        )
        return

    logger.error(
        "App command '%s' failed for user %s: %s",
        interaction.command.name if interaction.command else "?",
        interaction.user.id,
        cause,
        exc_info=cause,
    )

    msg = "❌ Unexpected error. Please try again."
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(msg, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)
    except Exception:
        pass


@bot.event
async def on_ready() -> None:
    logger.info("BullEyeBot is online as %s (id: %s)", bot.user, bot.user.id)
    if not getattr(bot, "_commands_synced", False):
        bot._commands_synced = True
        try:
            await bot.tree.sync()
            logger.info("Slash commands synced.")
        except discord.HTTPException as exc:
            logger.error("Failed to sync slash commands: %s", exc)


async def main() -> None:
    init_db()

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            logger.info("Loaded cog: %s", cog)

        bot.loop.create_task(scheduler_loop(bot))
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
