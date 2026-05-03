import asyncio
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord

from bot.db.repository import (
    get_active_alerts, deactivate_alert,
    get_all_active_schedules, update_last_sent_date,
)
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
        now = datetime.now(_TZ)
        now_str   = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        logger.debug("Scheduler tick at %s", now_str)

        await _check_alerts(bot)
        await _check_schedules(bot, now_str, today_str)


async def _process_alert(bot: discord.Client, loop: asyncio.AbstractEventLoop, alert: dict) -> None:
    data = await loop.run_in_executor(None, get_ticker_data, alert["ticker"])
    if data is None:
        return
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


async def _check_alerts(bot: discord.Client) -> None:
    loop = asyncio.get_event_loop()
    alerts = get_active_alerts()
    if not alerts:
        return
    tasks = [_process_alert(bot, loop, alert) for alert in alerts]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _process_schedule(bot: discord.Client, loop: asyncio.AbstractEventLoop, schedule: dict, today: str) -> None:
    try:
        user = await bot.fetch_user(int(schedule["discord_id"]))
        messages = await loop.run_in_executor(None, build_summary, schedule["user_id"], user.mention)
        for msg in messages:
            await user.send(msg)
        update_last_sent_date(schedule["user_id"], today)
        logger.info("Daily summary sent to user %s", schedule["discord_id"])
    except Exception as exc:
        logger.error("Failed to send daily summary to user %s: %s", schedule["discord_id"], exc)


async def _check_schedules(bot: discord.Client, now: str, today: str) -> None:
    loop = asyncio.get_event_loop()
    schedules = get_all_active_schedules()
    due = [s for s in schedules if s["last_sent_date"] != today and s["time"] == now]
    if not due:
        return
    tasks = [_process_schedule(bot, loop, s, today) for s in due]
    await asyncio.gather(*tasks, return_exceptions=True)
