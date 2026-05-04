import asyncio
import logging
import os
import sys

import discord
import discord.app_commands as app_commands
from discord.errors import PrivilegedIntentsRequired
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

PREFIX = os.getenv("PREFIX") or "!"

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
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
bot.heavy_semaphore = asyncio.Semaphore(3)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    cause = error
    while hasattr(cause, "original"):
        cause = cause.original

    if isinstance(cause, discord.NotFound) and cause.code == 10062:
        logger.warning(
            "App command '%s' received stale interaction (10062)",
            interaction.command.name if interaction.command else "?",
        )
        return

    logger.error(
        "App command '%s' failed: %s",
        interaction.command.name if interaction.command else "?",
        cause,
        exc_info=cause,
    )
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(
                "❌ Erro inesperado. Tente novamente.", ephemeral=True
            )
        except Exception:
            pass


@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    logger.info("BullEyeBot is online as %s (id: %s)", bot.user, bot.user.id)


def _root_cause(error: Exception) -> Exception:
    while hasattr(error, "original"):
        error = error.original
    return error


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} Missing argument: `{error.param.name}`.")
        return
    if isinstance(error, commands.CommandNotFound):
        return

    cause = _root_cause(error)

    if isinstance(cause, discord.NotFound) and cause.code == 10062:
        logger.warning(
            "Command '%s' received stale/expired interaction (10062) — "
            "token already invalid when bot processed it",
            ctx.command,
        )
        try:
            await ctx.channel.send(
                f"{ctx.author.mention} ⚠️ Your interaction expired. Please try the command again.",
                delete_after=8,
            )
        except Exception:
            pass
        return

    logger.error("Command '%s' failed: %s", ctx.command, cause, exc_info=cause)
    try:
        await ctx.send(f"{ctx.author.mention} ❌ Erro inesperado. Tente novamente.")
    except Exception:
        pass


async def main() -> None:
    init_db()

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            logger.info("Loaded cog: %s", cog)

        bot.loop.create_task(scheduler_loop(bot))
        try:
            await bot.start(DISCORD_TOKEN)
        except PrivilegedIntentsRequired:
            logger.error(
                "Message Content Intent is not enabled in the Discord Developer Portal. "
                "Go to discord.com/developers/applications, select your bot, open the 'Bot' tab, "
                "and enable 'Message Content Intent' under Privileged Gateway Intents."
            )
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
