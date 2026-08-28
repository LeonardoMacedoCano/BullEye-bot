# Setup

[← Back to README](../README.md)

## 1. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, click **Reset Token** and copy it — this is your `DISCORD_TOKEN`.
3. Enable **Message Content Intent** under Privileged Gateway Intents.
4. Under **OAuth2 → URL Generator**, select scope `bot` + `applications.commands` with permissions: Read Messages, Send Messages, Read Message History.
5. Open the generated URL to invite the bot to your server.

## 2. Run with Docker (recommended)

```bash
# Create a .env file with at minimum your bot token
echo "DISCORD_TOKEN=your_token_here" > .env

docker compose up -d
docker compose logs -f
```

## 3. Run locally

```bash
pip install -r requirements.txt

# Create a .env file with at minimum your bot token
echo "DISCORD_TOKEN=your_token_here" > .env

python -m bot.main
```

> Slash commands may take up to 1 hour to appear globally after the first start.

## 4. Run the tests

```bash
pytest
```

Covers formatting utilities, market normalization, database operations, and the use case layer (summary, dividends, tickers). A dedicated import smoke test verifies every module loads without error, catching broken imports before they reach the container.

---

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Bot token from the Developer Portal |
| `DATABASE_PATH` | No | `/data/bot.db` | Path to the SQLite file (inside the container) |
| `TIMEZONE` | No | `UTC` | Timezone for scheduled summaries and log timestamps — e.g. `America/Sao_Paulo` |
| `ENABLE_RESETDB` | No | — | Set to `1` to enable `/resetdb` (dev/testing only) |
| `PRICE_CACHE_TTL_MINUTES` | No | `5` | How long to cache price data. Lower = fresher data, more API calls. |
| `DIV_CACHE_TTL_HOURS` | No | `24` | How long to cache dividend/yield data. |
| `FEAR_GREED_CACHE_TTL_MINUTES` | No | `30` | How long to cache the Fear & Greed index. |

### Cache behaviour

All caches are **on-demand only** — data is fetched when a command needs it and stored until the TTL expires. If the bot is idle, no API calls are made. To force an immediate refresh, use `/refreshcache` (only re-fetches your own tickers — other users' cached data isn't touched).
