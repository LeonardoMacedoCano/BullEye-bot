# BullEye-bot — Project Guide

## Overview

Discord bot for financial market monitoring. Supports Brazilian B3 stocks, crypto, ETFs, and US stocks. Built with discord.py (hybrid commands), SQLite, yfinance, and brapi.dev.

## Architecture

```
bot/
├── main.py           # Bot setup, error handlers, on_ready
├── config.py         # Centralized env var parsing (timezone, cache TTLs)
├── scheduler.py      # Background loop: price alerts + daily summaries
├── utils.py          # defer() — must be called first in every app_command/hybrid_command
├── commands/         # One Cog per feature
│   ├── ticker.py     # add / remove / tickers
│   ├── alerts.py     # alert (price threshold)
│   ├── ceiling_cmd.py# ceiling (personal price ceiling)
│   ├── note_cmd.py   # note (free-text note per ticker)
│   ├── schedule_cmd.py # schedule / unschedule (daily summary)
│   ├── summary.py    # summary — heavy operation, uses semaphore
│   ├── dividends_cmd.py # dividends — heavy operation, uses semaphore
│   ├── cache_cmd.py  # refreshcache
│   ├── help_cmd.py   # help
│   └── resetdb_cmd.py # resetdb (dev only, requires ENABLE_RESETDB=1)
├── db/
│   ├── database.py   # SQLite schema init
│   └── repository.py # All DB access functions
├── application/       # Use cases — plain structured data (dicts/lists), no Discord objects
│   ├── summary_use_case.py   # build_summary
│   ├── dividends_use_case.py # get_dividends_rows
│   ├── ticker_use_case.py    # get_ticker_groups
│   └── market_cache.py       # DY yield / dividend info caching
├── shared/
│   ├── formatting.py     # display_name, currency, fmt, ansi_pct, render_table
│   ├── embeds.py         # EMBED_COLOR / COLOR_UP / COLOR_DOWN, wrap_table_field()
│   ├── summary_embed.py  # build_portfolio_embed, build_intelligence_embed
│   ├── dividends_embed.py# dividends_field_value, build_dividends_embed
│   ├── tickers_embed.py  # build_tickers_embed
│   ├── help_embed.py     # build_help_embed
│   └── cache_embed.py    # build_cache_embed
└── services/
    ├── market.py     # yfinance + brapi.dev, in-memory price cache
    ├── sentiment.py  # VIX, IBOV
    └── fear_greed.py # Fear & Greed index
```

## Project Standards

### Language
**All code, comments, logs, and user-facing strings must be in English.** No Portuguese anywhere in the codebase — not in messages sent to Discord, not in log messages, not in code comments, not in variable names.

The only exceptions are:
- The DB table `proventos` and its related internal function names (legacy schema, do not rename)
- Brazilian ticker suffixes like `.SA` (these are financial identifiers, not language)
- Brazilian finance terminology used as proper nouns in data (e.g. "JCP" in dividend type labels from the API)

### Discord Interactions — Critical Rules

Every `app_commands.command` **must** call `defer()` as its **very first line**, before any other awaitable or DB access:

```python
@app_commands.command(name="example")
async def example(self, interaction: discord.Interaction) -> None:
    if not await defer(interaction):
        return
    # ... rest of the handler
```

**Why:** Discord requires a response or defer within 3 seconds of a slash command. Any delay (DB, network, rate limiting) will cause "The application did not respond". `defer()` extends the window to 15 minutes and handles stale interaction errors (10062) automatically.

`defer()` is imported from `bot.utils` and handles `discord.NotFound` / `discord.HTTPException` gracefully, returning `False` on failure so the caller can exit early.

### Response Formatting — Embeds vs Plain Text

Use a `discord.Embed` (built via a `bot/shared/*_embed.py` module) when a command's output is **structured or multi-section data** — tables, multiple categories, or several distinct pieces of information (e.g. `/summary`, `/dividends`, `/help`, `/refreshcache`). Use plain `followup(interaction, text)` for **single-value confirmations and simple status messages** (e.g. `/alert`, `/ceiling`, `/note`, `/schedule`, `/ticker add|remove`) — wrapping a one-line confirmation in an embed adds visual weight without adding information.

Conventions for embed builders:
- One module per feature in `bot/shared/`, named `<feature>_embed.py`, exporting a `build_<feature>_embed(data) -> discord.Embed | None` function (return `None` when there's nothing to show — the caller falls back to a plain-text message).
- Shared constants/helpers (`EMBED_COLOR`, `COLOR_UP`, `COLOR_DOWN`, `wrap_table_field()`) live in `bot/shared/embeds.py` — import from there instead of redefining per module.
- Tables that need per-cell color (day change %, gains/losses) use `ansi_pct()` (`bot/shared/formatting.py`) inside a ` ```ansi ` code block wrapped with `wrap_table_field()`, which truncates rows to fit Discord's ~1024-char field limit.
- **Known limitation:** Discord's mobile apps (iOS/Android) don't render ANSI color codes in code blocks — only desktop/web do. Mobile users see the same text in the default color. This is a Discord client limitation, not something fixable from the bot's code.
- The use case layer (`bot/application/*_use_case.py`) returns plain structured data (dicts/lists), never pre-formatted embeds or Discord objects — command files wire use case output into the embed builder.

### Async / Concurrency

- Always use `asyncio.get_running_loop().run_in_executor(None, fn, *args)` for blocking I/O inside coroutines. Never use `asyncio.get_event_loop()` (deprecated in Python 3.10+).
- Wrap executor calls in `asyncio.wait_for()` for heavy operations (summary: 120s, dividends: 60s).
- Heavy commands (`summary`, `dividends`) must acquire `bot.heavy_semaphore` (limit: 3 concurrent) before the executor call.

### `on_ready()` and Sync

`bot.tree.sync()` is called **only once per process lifetime** via the `_commands_synced` flag. Do not add additional sync calls. Syncing on every reconnect floods the Discord API rate limit and delays interaction handling.

### Error Handling

- All exceptions inside command handlers must be caught and result in a user-facing message. Never let an error cause a silent no-response.
- Use `logger.exception()` (not `logger.error()`) when logging caught exceptions so the traceback is included.
- For external API failures (yfinance, brapi, fear & greed), log at `WARNING` level and return `None` — the caller handles the missing data gracefully.

### Caching

| Layer | Default TTL | Env Var | Location |
|-------|-------------|---------|----------|
| Price data | 5 min | `PRICE_CACHE_TTL_MINUTES` | In-memory dict + threading.Lock |
| Fear & Greed | 30 min | `FEAR_GREED_CACHE_TTL_MINUTES` | In-memory dict + threading.Lock |
| Dividends / proventos | 24 h | `DIV_CACHE_TTL_HOURS` | SQLite `ticker_price_cache` + `proventos` tables |

All caches are on-demand only — no proactive background fetching. To force a refresh, use the `/refreshcache` command.

### Database

- All DB access goes through `bot/db/repository.py`. Do not write SQL in command files.
- Use `INSERT OR IGNORE` for upserts where appropriate (see existing patterns).
- `get_or_create_user(discord_id)` must be called before any per-user DB operation.

### Adding a New Command

1. Create `bot/commands/mycommand.py` with a `Cog` class.
2. Add `defer(interaction)` as the first line of every `app_commands.command`.
3. Register the cog in `COGS` list in `bot/main.py`.
4. Add the command description to the relevant section in `bot/shared/help_embed.py`.
5. Use `asyncio.get_running_loop().run_in_executor()` for any blocking I/O.
6. If the response is structured/multi-section data, add a `bot/shared/mycommand_embed.py` (see [Response Formatting](#response-formatting--embeds-vs-plain-text)); otherwise use plain `followup(interaction, text)`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DISCORD_TOKEN` | — | Required. Bot token from Discord Developer Portal. |
| `DATABASE_PATH` | `/data/bot.db` | Path to SQLite file. |
| `TIMEZONE` | `UTC` | Timezone for scheduled summaries and log timestamps (e.g. `America/Sao_Paulo`). |
| `ENABLE_RESETDB` | `` | Set to `1` to enable the `!resetdb` dev command. |
| `PRICE_CACHE_TTL_MINUTES` | `5` | In-memory price data cache duration. Lower = fresher data, more API calls. |
| `DIV_CACHE_TTL_HOURS` | `24` | SQLite dividend/yield cache duration. |
| `FEAR_GREED_CACHE_TTL_MINUTES` | `30` | In-memory Fear & Greed index cache duration. |

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in DISCORD_TOKEN
python -m bot.main
```

## Docker

```bash
docker compose up -d
docker compose logs -f
```

## Ticker Conventions

| Input | Normalized | Market |
|-------|-----------|--------|
| `PETR4` | `PETR4.SA` | B3 Brazil |
| `BTC` | `BTC-USD` | Crypto |
| `AAPL` | `AAPL` | US stocks / ETFs |

Normalization happens in `services/market.py:normalize_ticker()`.
