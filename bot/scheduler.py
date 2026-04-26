import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from bot.db.repository import get_active_alerts, deactivate_alert, get_all_active_schedules
from bot.services.market import get_ticker_data
from bot.commands.summary import build_summary

logger = logging.getLogger(__name__)

_tz_name = os.getenv("TIMEZONE") or "UTC"
try:
    _TZ = ZoneInfo(_tz_name)
except ZoneInfoNotFoundError:
    logger.warning("Unknown TIMEZONE %r, falling back to UTC", _tz_name)
    _TZ = ZoneInfo("UTC")


async def scheduler_loop(bot: discord.Client) -> None:
    await bot.wait_until_ready()
    logger.info("Scheduler loop started (timezone: %s)", _tz_name)

    while not bot.is_closed():
        await asyncio.sleep(60)
        now = datetime.now(_TZ).strftime("%H:%M")
        logger.debug("Scheduler tick at %s", now)

        await _check_alerts(bot)
        await _check_schedules(bot, now)


async def _check_alerts(bot: discord.Client) -> None:
    alerts = get_active_alerts()
    for alert in alerts:
        data = get_ticker_data(alert["ticker"])
        if data is None:
            continue
        if data["current_price"] <= alert["target_price"]:
            deactivate_alert(alert["id"])
            try:
                user = await bot.fetch_user(int(alert["discord_id"]))
                await user.send(
                    f"{user.mention} Alert triggered: `{alert['ticker']}` is at "
                    f"**${data['current_price']:.2f}**, which reached your target of "
                    f"**${alert['target_price']:.2f}**."
                )
                logger.info(
                    "Alert %s triggered for user %s: %s <= %.2f",
                    alert["id"], alert["discord_id"], alert["ticker"], alert["target_price"],
                )
            except Exception as exc:
                logger.error("Failed to send alert DM to user %s: %s", alert["discord_id"], exc)


async def _check_schedules(bot: discord.Client, now: str) -> None:
    schedules = get_all_active_schedules()
    for schedule in schedules:
        if schedule["time"] != now:
            continue
        try:
            user = await bot.fetch_user(int(schedule["discord_id"]))
            for msg in build_summary(schedule["user_id"], user.mention):
                await user.send(msg)
            logger.info("Daily summary sent to user %s at %s", schedule["discord_id"], now)
        except Exception as exc:
            logger.error(
                "Failed to send daily summary to user %s: %s", schedule["discord_id"], exc
            )
