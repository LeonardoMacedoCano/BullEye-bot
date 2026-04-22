import logging
import discord
from discord.ext import commands

from bot.db.repository import get_or_create_user, list_tickers
from bot.services.market import get_ticker_data
from bot.services.fear_greed import get_fear_greed_index

logger = logging.getLogger(__name__)


def build_summary(user_id: int, discord_mention: str) -> str:
    tickers = list_tickers(user_id)
    if not tickers:
        return f"{discord_mention} You have no tickers configured. Use `!add <TICKER>` to get started."

    wallet = [row for row in tickers if row["category"] == "wallet"]
    watchlist = [row for row in tickers if row["category"] == "watchlist"]
    has_btc = any(row["ticker"].upper() == "BTC-USD" for row in tickers)

    lines = [f"{discord_mention} Your summary:\n"]

    def format_section(title: str, rows: list) -> list[str]:
        if not rows:
            return []
        section = [f"**{title}**"]
        for row in rows:
            data = get_ticker_data(row["ticker"])
            if data:
                section.append(
                    f"  {data['ticker']}: ${data['current_price']:.2f} "
                    f"| 30d High: ${data['high_30d']:.2f} "
                    f"| 30d Low: ${data['low_30d']:.2f}"
                )
            else:
                section.append(f"  {row['ticker']}: data unavailable")
        return section

    lines.extend(format_section("Wallet", wallet))
    if wallet and watchlist:
        lines.append("")
    lines.extend(format_section("Watchlist", watchlist))

    if has_btc:
        fg = get_fear_greed_index()
        if fg:
            lines.append(f"\n**Fear & Greed Index:** {fg['value']} ({fg['classification']})")
        else:
            lines.append("\n**Fear & Greed Index:** unavailable")

    return "\n".join(lines)


class SummaryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        async with ctx.typing():
            message = build_summary(user["id"], ctx.author.mention)
        await ctx.send(message)
        logger.info("Resume sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SummaryCog(bot))
