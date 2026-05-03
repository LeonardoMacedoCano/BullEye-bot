# BullEyeBot

A Discord bot for monitoring financial tickers. Track your portfolio and watchlist, receive price alerts, and get daily summaries — all through Discord commands.

---

## Features

- Add tickers to wallet or watchlist (`AAPL`, `PETR4`, `BTC`, ETFs, etc.)
- Day % change in every summary table
- Market sentiment header: VIX, IBOVESPA, and Bitcoin Fear & Greed Index
- Top Movers section: best and worst performers of the day and month
- Dividend radar: upcoming ex-dates and pay-dates for the next 60 days
- BR stocks show Dividend Yield (DY%) automatically
- Price alerts that trigger once when the target is reached
- Personal ceiling price with margin tracking
- Buy Opportunities section: tickers trading at or below your ceiling
- Daily summary delivered via DM at a scheduled time
- Brazilian B3 tickers and `BTC` are auto-formatted
- Each user has completely isolated data

---

## Commands

Both `!` prefix and `/` slash commands are supported. Slash commands (`/`) show autocomplete suggestions as you type.

| Command | Description |
|---------|-------------|
| `!add <TICKER> [wallet\|watchlist]` | Add a ticker (default: watchlist) |
| `!remove <TICKER>` | Remove a ticker and its alerts |
| `!list` | List all your tickers |
| `!alert <TICKER> <PRICE>` | Alert when price <= target (fires once) |
| `!ceiling <TICKER> <PRICE>` | Set your personal ceiling price for a ticker |
| `!ceiling <TICKER> clear` | Remove ceiling price |
| `!ceiling <TICKER>` | Show current ceiling price vs market |
| `!schedule HH:MM` | Schedule a daily summary DM |
| `!schedule` | Show your current schedule |
| `!unschedule` | Cancel your daily summary |
| `!summary` | Get your full summary now |
| `!dividends` | Show upcoming dividends (next 60 days) |
| `!help` | Show all commands |

> **Slash commands note:** autocomplete only works with `/`. The `!` prefix works for all commands but does not show suggestions.

**Ticker tips:** type `BTC` → auto-formats to `BTC-USD`; type `PETR4` → auto-formats to `PETR4.SA`.

---

## Summary layout

```
@you Your summary:
## Market
VIX   18.5  +2.1%  Moderate
IBOV  131.450  -0.8%
F&G   65  (Greed)

## Wallet
- **BR Stocks**
Ticker  Price       Day%    DY%     Ceiling
───────────────────────────────────────────
PETR4   R$38.10     +1.2%   6.54%   —
VALE3   R$56.40     -0.5%   8.21%   R$60.00 +6%

- **Crypto**
Ticker  Price         Day%    Ceiling
──────────────────────────────────────
BTC     $97,200.00    +3.1%   —

## Top Movers
         Day%            Month%
  Best:  PETR4 +1.2%     VALE3 +8.4%
  Worst: VALE3 -0.5%     PETR4 -2.1%

## Upcoming Dividends
Ticker  Ex-Date     Pay-Date    Amount
──────────────────────────────────────
PETR4   2026-05-15  2026-05-30  R$1.25

## Buy Opportunities
Ticker  Price      Ceiling    Margin  In
────────────────────────────────────────
VALE3   R$56.40    R$60.00    +6.4%   wallet
```

---

## Setup

### 1. Create a Discord bot

1. Go to the Discord Developer Portal and create a new application.
2. Under **Bot**, click "Reset Token" and copy it — this is your `DISCORD_TOKEN`.
3. Enable **Message Content Intent** under Privileged Gateway Intents.
4. Under **OAuth2 > URL Generator**, select scope `bot` + `applications.commands` with permissions: Read Messages, Send Messages, Read Message History.
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

> **Slash commands propagation:** after the first start, Discord may take up to 1 hour to show `/` commands globally.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | Yes | — | Discord bot token |
| `PREFIX` | No | `!` | Command prefix |
| `DATABASE_PATH` | No | `/data/bot.db` | Path to SQLite database inside the container |
| `BULLEYEBOT_SOURCE_PATH` | No | `.` | Host path to source code for Docker build context |
| `TIMEZONE` | No | `UTC` | Timezone for scheduled summaries (e.g. `America/Sao_Paulo`) |
