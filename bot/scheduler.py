import asyncio
import logging
from datetime import datetime

import discord

from bot.config import TIMEZONE as _TZ, TIMEZONE_NAME as _tz_name
from bot.db.repository import (
    get_active_alerts, deactivate_alert,
    get_all_active_schedules, update_last_sent_date,
    get_active_fgi_alerts, deactivate_fgi_alert,
)
from bot.services.market import get_ticker_data, get_cache_stats
from bot.services.fear_greed import get_fear_greed_index
from bot.application.summary_use_case import build_summary
from bot.shared.context import new_request_id

logger = logging.getLogger(__name__)

_STATS_LOG_INTERVAL = 30  # ticks (minutes)


async def scheduler_loop(bot: discord.Client) -> None:
    await bot.wait_until_ready()
    logger.info("Scheduler loop started (timezone: %s)", _tz_name)

    tick = 0
    while not bot.is_closed():
        await asyncio.sleep(60)
        now = datetime.now(_TZ)
        now_str   = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        logger.debug("Scheduler tick at %s", now_str)

        tick += 1
        if tick % _STATS_LOG_INTERVAL == 0:
            stats = get_cache_stats()
            logger.info(
                "Cache stats — hits: %d, misses: %d, errors: %d",
                stats["hits"], stats["misses"], stats["errors"],
            )

        await _check_alerts(bot)
        await _check_fgi_alerts(bot)
        await _check_schedules(bot, now_str, today_str)


async def _process_alert(bot: discord.Client, loop: asyncio.AbstractEventLoop, alert: dict) -> None:
    rid = new_request_id()
    data = await loop.run_in_executor(None, get_ticker_data, alert["ticker"])
    if data is None:
        return
    if data["current_price"] <= alert["target_price"]:
        await loop.run_in_executor(None, deactivate_alert, alert["id"])
        try:
            user = await bot.fetch_user(int(alert["discord_id"]))
            await user.send(
                f"{user.mention} Alert triggered: `{alert['ticker']}` is at "
                f"**${data['current_price']:.2f}**, which reached your target of "
                f"**${alert['target_price']:.2f}**."
            )
            logger.info(
                "[%s] Alert %s triggered for user %s: %s <= %.2f",
                rid, alert["id"], alert["discord_id"], alert["ticker"], alert["target_price"],
            )
        except Exception as exc:
            logger.error("Failed to send alert DM to user %s: %s", alert["discord_id"], exc)


_ALERT_CONCURRENCY = 10


async def _check_alerts(bot: discord.Client) -> None:
    loop = asyncio.get_running_loop()
    alerts = await loop.run_in_executor(None, get_active_alerts)
    if not alerts:
        return
    sem = asyncio.Semaphore(_ALERT_CONCURRENCY)

    async def _bounded(alert: dict) -> None:
        async with sem:
            await _process_alert(bot, loop, alert)

    tasks = [_bounded(alert) for alert in alerts]
    await asyncio.gather(*tasks, return_exceptions=True)


async def _check_fgi_alerts(bot: discord.Client) -> None:
    loop = asyncio.get_running_loop()
    alerts = await loop.run_in_executor(None, get_active_fgi_alerts)
    if not alerts:
        return
    fgi = await loop.run_in_executor(None, get_fear_greed_index)
    if fgi is None:
        return
    for alert in alerts:
        if fgi["value"] <= alert["target_value"]:
            await loop.run_in_executor(None, deactivate_fgi_alert, alert["id"])
            try:
                user = await bot.fetch_user(int(alert["discord_id"]))
                await user.send(
                    f"{user.mention} Fear & Greed alert triggered: index is at "
                    f"**{fgi['value']}** ({fgi['classification']}), which reached your target of "
                    f"**{alert['target_value']}**."
                )
                logger.info(
                    "FGI alert %s triggered for user %s: %d <= %d",
                    alert["id"], alert["discord_id"], fgi["value"], alert["target_value"],
                )
            except Exception as exc:
                logger.error("Failed to send FGI alert DM to user %s: %s", alert["discord_id"], exc)


async def _process_schedule(bot: discord.Client, loop: asyncio.AbstractEventLoop, schedule: dict, today: str) -> None:
    rid = new_request_id()
    try:
        user = await bot.fetch_user(int(schedule["discord_id"]))
        messages = await loop.run_in_executor(None, build_summary, schedule["user_id"], user.mention)
        for msg in messages:
            await user.send(msg)
        await loop.run_in_executor(None, update_last_sent_date, schedule["user_id"], today)
        logger.info("[%s] Daily summary sent to user %s", rid, schedule["discord_id"])
    except Exception as exc:
        logger.error("[%s] Failed to send daily summary to user %s: %s", rid, schedule["discord_id"], exc)


async def _check_schedules(bot: discord.Client, now: str, today: str) -> None:
    loop = asyncio.get_running_loop()
    schedules = await loop.run_in_executor(None, get_all_active_schedules)
    due = [s for s in schedules if s["last_sent_date"] != today and s["time"] == now]
    if not due:
        return
    tasks = [_process_schedule(bot, loop, s, today) for s in due]
    await asyncio.gather(*tasks, return_exceptions=True)
