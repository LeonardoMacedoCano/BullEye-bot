import asyncio
import logging
import os
import sys

import discord
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
]

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready() -> None:
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
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
