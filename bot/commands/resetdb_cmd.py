import logging
import os

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.database import init_db, get_connection
from bot.utils import defer, followup, mention

logger = logging.getLogger(__name__)

_TABLES = [
    "proventos",
    "ticker_price_cache",
    "alerts",
    "fgi_alerts",
    "user_fgi_ceilings",
    "user_tickers",
    "schedules",
    "tickers",
    "users",
]


class ResetDbCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="resetdb", description="[DEV] Drop and recreate all database tables (requires ENABLE_RESETDB=1)")
    async def resetdb(self, interaction: discord.Interaction) -> None:
        if not await defer(interaction, ephemeral=True):
            return
        m = mention(interaction)
        if not os.getenv("ENABLE_RESETDB"):
            await followup(interaction, f"{m} ❌ Command disabled.", ephemeral=True)
            return
        conn = get_connection()
        try:
            for table in _TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
        finally:
            conn.close()
        init_db()
        await followup(interaction, f"{m} ✅ Database reset and recreated with the new schema.", ephemeral=True)
        logger.info("Database reset by user %s", interaction.user.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ResetDbCog(bot))
