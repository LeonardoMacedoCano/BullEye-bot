import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, get_ticker_category, get_ticker_row, set_user_ceiling, clear_user_ceiling
from bot.services.market import normalize_ticker, get_ticker_data

logger = logging.getLogger(__name__)


def _sym(ticker: str) -> str:
    return "R$" if ticker.upper().endswith(".SA") else "$"


class CeilingCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.hybrid_command(name="ceiling")
    async def ceiling(self, ctx: commands.Context, ticker: str, value: str = None) -> None:
        await ctx.defer()
        original = ticker.upper().strip()
        ticker = normalize_ticker(original)
        user = get_or_create_user(str(ctx.author.id))

        if not get_ticker_category(user["id"], ticker):
            await ctx.send(
                f"{ctx.author.mention} `{ticker}` is not in your list. Add it first with `!add`."
            )
            return

        sym = _sym(ticker)

        if value is None:
            row = get_ticker_row(user["id"], ticker)
            user_ceiling = row["user_ceiling"] if row else None
            if user_ceiling is None:
                await ctx.send(f"{ctx.author.mention} No ceiling set for `{ticker}`.")
                return
            async with ctx.typing():
                data = get_ticker_data(ticker)
            if data:
                price = data["current_price"]
                margin = (user_ceiling - price) / price * 100
                sign = "+" if margin >= 0 else ""
                status = "below ceiling" if margin >= 0 else "above ceiling"
                await ctx.send(
                    f"{ctx.author.mention} `{ticker}` ceiling: {sym}{user_ceiling:,.2f} — "
                    f"Current: {sym}{price:,.2f} ({sign}{margin:.1f}% {status})"
                )
            else:
                await ctx.send(f"{ctx.author.mention} `{ticker}` ceiling: {sym}{user_ceiling:,.2f}")
            return

        if value.lower() == "clear":
            clear_user_ceiling(user["id"], ticker)
            await ctx.send(f"{ctx.author.mention} Ceiling removed for `{ticker}`.")
            logger.info("User %s cleared ceiling for %s", ctx.author.id, ticker)
            return

        try:
            ceiling_val = float(value.replace(",", "."))
            if ceiling_val <= 0:
                raise ValueError
        except ValueError:
            await ctx.send(
                f"{ctx.author.mention} Invalid price `{value}`. Use a positive number or `clear`."
            )
            return

        set_user_ceiling(user["id"], ticker, ceiling_val)
        await ctx.send(f"{ctx.author.mention} Ceiling set: `{ticker}` ≤ {sym}{ceiling_val:,.2f}.")
        logger.info("User %s set ceiling for %s to %.2f", ctx.author.id, ticker, ceiling_val)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CeilingCog(bot))
