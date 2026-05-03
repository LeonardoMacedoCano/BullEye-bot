import logging
from discord.ext import commands

logger = logging.getLogger(__name__)


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="help")
    async def help_cmd(self, ctx: commands.Context) -> None:
        await ctx.defer()
        p = ctx.prefix
        lines = [
            f"{ctx.author.mention} **BullEyeBot — Commands**\n",
            f"`{p}add <TICKER> [wallet|watchlist]` — Add a ticker (default: watchlist)",
            f"`{p}remove <TICKER>` — Remove a ticker and its alerts",
            f"`{p}list` — List all your tickers",
            f"`{p}alert <TICKER> <PRICE>` — Alert when price reaches or drops below target (fires once)",
            f"`{p}ceiling <TICKER> <PRICE>` — Set your personal ceiling price for a ticker",
            f"`{p}ceiling <TICKER> clear` — Remove ceiling price",
            f"`{p}ceiling <TICKER>` — Show current ceiling price",
            f"`{p}schedule HH:MM` — Schedule a daily summary DM",
            f"`{p}schedule` — Show your current schedule",
            f"`{p}unschedule` — Cancel your daily summary",
            f"`{p}summary` — Get your current summary",
            f"`{p}dividends` — Show upcoming dividends (next 60 days)",
            f"`{p}help` — Show this message",
            "\n**Ticker tips:** Brazilian B3 stocks auto-format (`PETR4` → `PETR4.SA`). `BTC` auto-formats to `BTC-USD`.",
        ]
        await ctx.send("\n".join(lines))
        logger.info("Help sent to user %s", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(HelpCog(bot))
