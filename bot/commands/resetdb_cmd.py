import logging
import os
from discord.ext import commands

from bot.db.database import init_db, get_connection

logger = logging.getLogger(__name__)

_TABLES = [
    "proventos",
    "ticker_price_cache",
    "alerts",
    "user_tickers",
    "schedules",
    "tickers",
    "users",
]


class ResetDbCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="resetdb")
    async def resetdb(self, ctx: commands.Context) -> None:
        if not os.getenv("ENABLE_RESETDB"):
            await ctx.send(f"{ctx.author.mention} ❌ Command disabled.")
            return
        conn = get_connection()
        try:
            for table in _TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.commit()
        finally:
            conn.close()
        init_db()
        await ctx.send(f"{ctx.author.mention} ✅ Database reset and recreated with the new schema.")
        logger.info("Database reset by user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ResetDbCog(bot))
