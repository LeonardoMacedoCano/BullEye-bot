# BullEyeBot

A Discord bot for monitoring financial tickers. Track your portfolio and watchlist, set price alerts, and receive daily summaries — all through Discord commands.

---

## Features

- Add tickers to your wallet or watchlist (e.g. PETR4.SA, VALE3.SA, BTC-USD)
- Get real-time price data with 30-day highs and lows
- Set price alerts that trigger once when the target is reached
- Schedule a daily summary delivered via DM
- Request a manual summary at any time
- Bitcoin tickers automatically include the Fear and Greed Index
- Full multi-user support with isolated data per user

---

## Commands

| Command | Description | Example |
|---------|-------------|---------|
| `!add <TICKER> [wallet\|watchlist]` | Add a ticker (default: watchlist) | `!add AAPL wallet` |
| `!remove <TICKER>` | Remove a ticker and its alerts | `!remove AAPL` |
| `!list` | List all your tickers | `!list` |
| `!alert <TICKER> <PRICE>` | Set a price alert (triggers when price <= target) | `!alert AAPL 150.00` |
| `!schedule HH:MM` | Schedule a daily summary DM | `!schedule 08:00` |
| `!resume` | Get your summary right now | `!resume` |

### Notes

- Tickers must be valid symbols recognized by Yahoo Finance (e.g. `AAPL`, `PETR4.SA`, `BTC-USD`).
- Company names are not accepted.
- Alerts fire only once and become inactive after triggering.
- Each user has completely isolated data.

---

## Example Usage

```
> !add BTC-USD
@you Ticker BTC-USD added to watchlist.

> !add AAPL wallet
@you Ticker AAPL added to wallet.

> !alert AAPL 170.00
@you Alert set: AAPL <= $170.00. You will be notified once when this condition is met.

> !schedule 09:00
@you Daily summary scheduled at 09:00. You will receive a DM every day at this time.

> !resume
@you Your summary:

**Wallet**
  AAPL: $172.50 | 30d High: $185.00 | 30d Low: $160.00

**Watchlist**
  BTC-USD: $67420.00 | 30d High: $72000.00 | 30d Low: $59000.00

**Fear & Greed Index:** 62 (Greed)
```

---

## Setting Up a Discord Bot

1. Go to the Discord Developer Portal and log in.
2. Click "New Application" and give it a name.
3. Navigate to the "Bot" section in the left sidebar.
4. Click "Add Bot" and confirm.
5. Under "Token", click "Reset Token" and copy the token. This is your `DISCORD_TOKEN`.
6. Under "Privileged Gateway Intents", enable **Message Content Intent**.
7. Navigate to "OAuth2" > "URL Generator".
8. Select the `bot` scope and the following permissions:
   - Read Messages / View Channels
   - Send Messages
   - Read Message History
9. Copy the generated URL, open it in your browser, and invite the bot to your server.

---

## Running with Docker

### Prerequisites

- Docker and Docker Compose installed
- A valid Discord bot token (see above)

### Steps

1. Clone or copy this repository.

2. Create a `.env` file in the project root:

```
DISCORD_TOKEN=your_discord_bot_token_here
DATABASE_PATH=/data/bot.db
BULLEYEBOT_DATA_PATH=/mnt/user/appdata/bulleyebot
```

3. Build and start the bot:

```bash
docker-compose up -d
```

4. Check the logs:

```bash
docker-compose logs -f
```

5. Stop the bot:

```bash
docker-compose down
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Your Discord bot token |
| `DATABASE_PATH` | No | `/data/bot.db` | Path to the SQLite database file inside the container |
| `BULLEYEBOT_DATA_PATH` | No | named volume `bot_data` | Host path mounted to `/data` in the container (e.g. `/opt/bulleyebot/data`) |

If `BULLEYEBOT_DATA_PATH` is set, the database is persisted at that host path. If omitted, a Docker named volume `bot_data` is used automatically.

---

## Architecture

```
BullEye-bot/
├── bot/
│   ├── main.py              # Entry point: bot initialization, cog loading, scheduler start
│   ├── scheduler.py         # Background asyncio loop: checks alerts and schedules every 60s
│   ├── commands/
│   │   ├── ticker.py        # !add, !remove, !list
│   │   ├── alerts.py        # !alert
│   │   ├── schedule_cmd.py  # !schedule
│   │   └── summary.py       # !resume + shared build_summary function
│   ├── services/
│   │   ├── market.py        # Yahoo Finance integration via yfinance
│   │   └── fear_greed.py    # Fear & Greed Index via alternative.me API
│   └── db/
│       ├── database.py      # SQLite connection and schema initialization
│       └── repository.py    # All CRUD operations (no ORM)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

### Component Responsibilities

- **Commands**: Each command group is a `discord.py` Cog, loaded independently at startup.
- **Services**: Stateless functions that call external APIs (Yahoo Finance, Fear & Greed).
- **Database**: Plain `sqlite3` with parameterized queries. Schema is auto-created on first run.
- **Scheduler**: An async task started at bot startup. Runs an infinite loop sleeping 60 seconds between ticks. Checks all active alerts and scheduled summaries on each tick.

### Data Flow

- Price alerts: scheduler fetches current price for each active alert. If `price <= target`, it sends a DM and marks the alert inactive.
- Scheduled summaries: scheduler compares current `HH:MM` to each user's configured time. On match, it builds and sends a full summary DM.
- Manual summary (`!resume`): builds the same summary synchronously in response to the command.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `discord.py` | Discord bot framework |
| `yfinance` | Yahoo Finance market data |
| `requests` | HTTP client for Fear & Greed API |
| `python-dotenv` | Loading environment variables from `.env` |
