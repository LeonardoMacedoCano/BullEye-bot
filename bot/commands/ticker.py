import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from bot.db.repository import get_or_create_user, add_ticker, remove_ticker, list_tickers, get_ticker_category
from bot.services.market import validate_ticker, normalize_ticker, get_ticker_subcategory, SUBCATEGORY_LABELS, SUBCATEGORY_ORDER
from bot.utils import defer, followup, mention, perf_start, perf_log
from bot.shared.formatting import MSG_LIMIT, display_name, currency, render_table, group_by_subcategory

logger = logging.getLogger(__name__)

VALID_CATEGORIES = ("wallet", "watchlist")


def _fmt_price(price: float | None, ticker: str) -> str:
    if price is None:
        return "—"
    sym = currency(ticker)
    return f"{sym}{price:,.2f}"


def _truncate_note(note: str | None, max_len: int = 80) -> str:
    if not note:
        return "—"
    return note if len(note) <= max_len else note[:max_len - 1] + "…"


def _build_tickers_section(title: str, rows: list) -> list[str]:
    groups = group_by_subcategory(rows, SUBCATEGORY_ORDER)
    use_groups = len(groups) > 1 or (len(groups) == 1 and groups[0][0] is not None)

    messages: list[str] = []
    heading_emitted = False

    for key, group_rows in groups:
        label = SUBCATEGORY_LABELS.get(key, key) if key else None

        headers = ["Ticker", "Ceiling", "Alert", "Note"]
        data_rows = []
        for row in group_rows:
            ticker = row["ticker"]
            data_rows.append([
                display_name(ticker),
                _fmt_price(row["user_ceiling"], ticker),
                _fmt_price(row["alert_price"], ticker),
                _truncate_note(row["note"]),
            ])

        table_str = render_table(headers, data_rows)
        if not table_str:
            continue

        parts = []
        if not heading_emitted:
            parts.append(f"# {title}")
            heading_emitted = True
        if use_groups and label:
            parts.append(f"- **{label}**")
        parts.append(f"```\n{table_str}\n```")
        block = "\n".join(parts)

        if messages and len(messages[-1]) + 1 + len(block) <= MSG_LIMIT:
            messages[-1] += "\n" + block
        else:
            messages.append(block)

    return messages


class TickerCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="add", description="Add a ticker to your wallet or watchlist")
    @app_commands.describe(
        ticker="Ticker symbol (e.g. AAPL, BTC, PETR4)",
        category="Which list to add to (default: watchlist)",
    )
    @app_commands.choices(category=[
        app_commands.Choice(name="wallet", value="wallet"),
        app_commands.Choice(name="watchlist", value="watchlist"),
    ])
    async def add(
        self,
        interaction: discord.Interaction,
        ticker: str,
        category: app_commands.Choice[str] = None,
    ) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        cat_value = category.value if category is not None else "watchlist"

        original = ticker.upper().strip()
        ticker = normalize_ticker(original)

        def _validate():
            valid = validate_ticker(ticker)
            subcategory = get_ticker_subcategory(ticker) if valid else None
            return valid, subcategory

        loop = asyncio.get_running_loop()
        try:
            valid, subcategory = await loop.run_in_executor(None, _validate)
        except Exception:
            logger.exception("Error validating ticker %s", ticker)
            await followup(interaction, f"{m} ❌ Error validating ticker. Please try again.")
            return

        if not valid:
            await followup(interaction, f"{m} Ticker `{ticker}` not found.")
            return

        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        existing = await loop.run_in_executor(None, get_ticker_category, user["id"], ticker)
        if existing == cat_value:
            await followup(interaction, f"{m} `{ticker}` is already in your **{cat_value}**.")
            return
        if existing:
            await followup(
                interaction,
                f"{m} `{ticker}` is already in your **{existing}**. "
                f"Remove it first with `/remove {ticker}`.",
            )
            return

        await loop.run_in_executor(None, add_ticker, user["id"], ticker, cat_value, subcategory)

        sub_label = f" ({SUBCATEGORY_LABELS[subcategory]})" if subcategory in SUBCATEGORY_LABELS else ""
        if ticker != original:
            await followup(
                interaction,
                f"{m} `{original}` interpreted as `{ticker}`. Added to **{cat_value}**{sub_label}.",
            )
        else:
            await followup(interaction, f"{m} Ticker `{ticker}` added to **{cat_value}**{sub_label}.")
        logger.info("User %s added ticker %s to %s (%s)", interaction.user.id, ticker, cat_value, subcategory)
        perf_log(logger, "add", t0)

    @app_commands.command(name="remove", description="Remove a ticker from your list")
    @app_commands.describe(ticker="Ticker symbol to remove")
    async def remove(self, interaction: discord.Interaction, ticker: str) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        original = ticker.upper().strip()
        ticker = normalize_ticker(original)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        count = await loop.run_in_executor(None, remove_ticker, user["id"], ticker)
        if count == 0:
            await followup(interaction, f"{m} Ticker `{ticker}` not found in your list.")
        else:
            await followup(interaction, f"{m} Ticker `{ticker}` removed.")
            logger.info("User %s removed ticker %s", interaction.user.id, ticker)
        perf_log(logger, "remove", t0)

    @app_commands.command(name="tickers", description="Show all your tickers with ceiling, alerts and notes")
    async def tickers_cmd(self, interaction: discord.Interaction) -> None:
        t0 = perf_start()
        if not await defer(interaction):
            return
        m = mention(interaction)
        loop = asyncio.get_running_loop()
        user = await loop.run_in_executor(None, get_or_create_user, str(interaction.user.id))
        rows = await loop.run_in_executor(None, list_tickers, user["id"])

        if not rows:
            await followup(
                interaction,
                f"{m} Your ticker list is empty. Use `/add <TICKER>` to add one.",
            )
            return

        wallet = [row for row in rows if row["category"] == "wallet"]
        watchlist = [row for row in rows if row["category"] == "watchlist"]

        sections: list[str] = []
        if wallet:
            sections.extend(_build_tickers_section("💼 Wallet", wallet))
        if watchlist:
            sections.extend(_build_tickers_section("👀 Watchlist", watchlist))

        packed: list[str] = []
        current = ""
        for s in sections:
            if not current:
                current = s
            elif len(current) + 1 + len(s) <= MSG_LIMIT:
                current += "\n" + s
            else:
                packed.append(current)
                current = s
        if current:
            packed.append(current)

        packed[0] = f"{m} Your tickers:\n{packed[0]}"
        for msg in packed:
            await followup(interaction, msg)

        perf_log(logger, "tickers", t0)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TickerCog(bot))
