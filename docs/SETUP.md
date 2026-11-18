# Setup

[← Back to README](../README.md)

## 1. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, click **Reset Token** and copy it — this is your `DISCORD_TOKEN`.
3. Enable **Message Content Intent** under Privileged Gateway Intents.
4. Under **OAuth2 → URL Generator**, select scope `bot` + `applications.commands` with permissions: Read Messages, Send Messages, Read Message History.
5. Open the generated URL to invite the bot to your server.

## 2. Create a brapi.dev token

Dividend/proventos data (`/dividends`) comes from brapi.dev, which requires an API token.

1. Create a free account at [brapi.dev](https://brapi.dev/dashboard).
2. Copy your token from the dashboard — this is your `BRAPI_TOKEN`.

Without this token, dividend/proventos fetches are skipped and logged as a warning; the rest of the bot (prices, summaries, alerts) works normally.

## 3. Run with Docker (recommended)

```bash
cp .env.example .env
# edit .env and fill in DISCORD_TOKEN and BRAPI_TOKEN

docker compose up -d
docker compose logs -f
```

## 4. Run locally

```bash
pip install -r requirements.txt

cp .env.example .env
# edit .env and fill in DISCORD_TOKEN and BRAPI_TOKEN

python -m bot.main
```

> Slash commands may take up to 1 hour to appear globally after the first start.

## 5. Run the tests

```bash
pytest
```

Covers formatting utilities, market normalization, database operations, and the use case layer (summary, dividends, tickers). A dedicated import smoke test verifies every module loads without error, catching broken imports before they reach the container.

These same tests run automatically on every push and pull request via GitHub Actions (`.github/workflows/ci.yml`).

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from the Developer Portal |
| `BRAPI_TOKEN` | Yes | — | API token from the [brapi.dev dashboard](https://brapi.dev/dashboard), needed for dividend/proventos data |
| `DATABASE_PATH` | No | `/data/bot.db` | Path to the SQLite file (inside the container) |
| `TIMEZONE` | No | `UTC` | Timezone for scheduled summaries and log timestamps — e.g. `America/Sao_Paulo` |
| `ENABLE_RESETDB` | No | — | Set to `1` to enable `/resetdb` (dev/testing only) |
| `PRICE_CACHE_TTL_MINUTES` | No | `5` | How long to cache price data. Lower = fresher data, more API calls. |
| `DIV_CACHE_TTL_HOURS` | No | `24` | How long to cache dividend/yield data. |
| `FEAR_GREED_CACHE_TTL_MINUTES` | No | `30` | How long to cache the Fear & Greed index. |

### Cache behaviour

All caches are **on-demand only** — data is fetched when a command needs it and stored until the TTL expires. If the bot is idle, no API calls are made. To force an immediate refresh, use `/refreshcache` (only re-fetches your own tickers — other users' cached data isn't touched).
