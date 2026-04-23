import re
import logging
from discord.ext import commands

from bot.db.repository import get_or_create_user, set_schedule, get_schedule, deactivate_schedule

logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")


class ScheduleCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command(name="schedule")
    async def schedule(self, ctx: commands.Context, time: str = None) -> None:
        user = get_or_create_user(str(ctx.author.id))

        if time is None:
            row = get_schedule(user["id"])
            if row:
                await ctx.send(
                    f"{ctx.author.mention} Your daily summary is scheduled at **{row['time']}**."
                )
            else:
                await ctx.send(
                    f"{ctx.author.mention} No schedule set. Use `!schedule HH:MM` to set one."
                )
            return

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

        set_schedule(user["id"], time)
        await ctx.send(f"{ctx.author.mention} Daily summary scheduled at **{time}**.")
        logger.info("User %s set daily schedule at %s", ctx.author.id, time)

    @commands.command(name="unschedule")
    async def unschedule(self, ctx: commands.Context) -> None:
        user = get_or_create_user(str(ctx.author.id))
        count = deactivate_schedule(user["id"])
        if count == 0:
            await ctx.send(f"{ctx.author.mention} You have no active schedule to cancel.")
        else:
            await ctx.send(f"{ctx.author.mention} Daily summary cancelled.")
            logger.info("User %s cancelled their daily schedule", ctx.author.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScheduleCog(bot))
