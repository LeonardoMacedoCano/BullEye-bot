# BullEyeBot

A Discord bot for monitoring financial tickers. Track your portfolio and watchlist, receive price alerts, and get daily summaries — all through Discord commands.

---

## Features

- Add tickers to wallet or watchlist (e.g. `AAPL`, `PETR4.SA`, `BTC-USD`)
- Real-time price with 30-day high and low
- Price alerts that trigger once when the target is reached
- Daily summary delivered via DM at a scheduled time
- Fear & Greed Index shown alongside Bitcoin
- Brazilian B3 tickers and `BTC` are auto-formatted
- Each user has completely isolated data

---

## Commands

| Command | Description |
|---------|-------------|
| `!add <TICKER> [wallet\|watchlist]` | Add a ticker (default: watchlist) |
| `!remove <TICKER>` | Remove a ticker and its alerts |
| `!list` | List all your tickers |
| `!alert <TICKER> <PRICE>` | Alert when price <= target (fires once) |
| `!schedule HH:MM` | Schedule a daily summary DM |
| `!schedule` | Show your current schedule |
| `!unschedule` | Cancel your daily summary |
| `!resume` | Get your summary now |
| `!help` | Show all commands |

**Ticker tips:** type `BTC` and it becomes `BTC-USD`; type `PETR4` and it becomes `PETR4.SA`.

---

## Example

```
!add BTC
> BTC interpreted as BTC-USD. Added to watchlist.

!add PETR4 wallet
> PETR4 interpreted as PETR4.SA. Added to wallet.

!alert AAPL 170.00
> Alert set: AAPL <= $170.00.

!schedule 09:00
> Daily summary scheduled at 09:00.

!resume
> Watchlist
> Ticker    Price        H (30d)      L (30d)      F&G
> ─────────────────────────────────────────────────────
> BTC       $78,334.98   $78,502.91   $64,971.71   46 (Fear)
```

---

## Setup

### 1. Create a Discord bot

1. Go to the Discord Developer Portal and create a new application.
2. Under **Bot**, click "Reset Token" and copy it — this is your `DISCORD_TOKEN`.
3. Enable **Message Content Intent** under Privileged Gateway Intents.
4. Under **OAuth2 > URL Generator**, select scope `bot` with permissions: Read Messages, Send Messages, Read Message History.
5. Open the generated URL to invite the bot to your server.

### 2. Configure and run

Create a `.env` file:

```
DISCORD_TOKEN=your_token_here
```

Start with Docker:

```bash
docker-compose up -d
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `PREFIX` | No | `!` | Command prefix |
| `DATABASE_PATH` | No | `/data/bot.db` | Path to SQLite database inside the container |
| `BULLEYEBOT_SOURCE_PATH` | No | `.` | Host path to source code for Docker build context |
| `TIMEZONE` | No | `UTC` | Timezone for scheduled summaries (e.g. `America/Sao_Paulo`) |
