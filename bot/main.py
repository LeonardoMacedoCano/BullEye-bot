import asyncio
import logging
import os
import sys

import discord
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
    "bot.commands.help_cmd",
]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)


@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    logger.info("BullEyeBot is online as %s (id: %s)", bot.user, bot.user.id)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"{ctx.author.mention} Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        logger.error("Unhandled command error: %s", error)


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
