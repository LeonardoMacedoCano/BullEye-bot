import re
import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, set_schedule, get_schedule

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="schedule")
    async def schedule(self, ctx: commands.Context, time: str) -> None:
        match = _TIME_RE.match(time)
        if not match:
            await ctx.send(
                f"{ctx.author.mention} Invalid time format. Use `HH:MM` (e.g. `!schedule 08:30`)."
            )
            return

        hour, minute = int(match.group(1)), int(match.group(2))
        if hour > 23 or minute > 59:
            await ctx.send(
                f"{ctx.author.mention} Invalid time `{time}`. Hour must be 00-23 and minute 00-59."
            )
            return

        user = get_or_create_user(str(ctx.author.id))
        set_schedule(user["id"], time)
        await ctx.send(
            f"{ctx.author.mention} Daily summary scheduled at **{time}**. "
            f"You will receive a DM every day at this time."
        )
        logger.info("User %s set daily schedule at %s", ctx.author.id, time)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScheduleCog(bot))
