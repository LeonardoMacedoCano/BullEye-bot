# BullEyeBot

> Your personal financial market assistant on Discord. Track stocks, crypto, and ETFs — get price alerts, dividend radars, and daily summaries without leaving your server.

Supports Brazilian B3 stocks, US equities, ETFs, and cryptocurrencies. Pulls live data from [yfinance](https://github.com/ranaroussi/yfinance) and [brapi.dev](https://brapi.dev), with a local cache to keep responses fast and API calls low.

Each user has their own isolated data — add your own tickers, set your own alerts, schedule your own summaries.

---

## What it does

| Feature | Description |
|---------|-------------|
| **Portfolio tracking** | Organize tickers into a **wallet** (things you own) and a **watchlist** (things you're watching) |
| **Price alerts** | Set a target price and get a DM the moment it's hit — fires once and deactivates automatically |
| **Ceiling prices** | Mark your personal buy target for a ticker and see how far the market is from it at a glance |
| **Ticker notes** | Attach a free-text note to any ticker — visible in `/tickers` for quick context |
| **Daily summaries** | Schedule a full market overview delivered to your DMs every day at a time you choose |
| **Dividend radar** | Upcoming ex-dates, pay-dates, types (Dividendo, JCP, Rendimento), and amounts for the next 60 days |
| **Market sentiment** | VIX, IBOVESPA, and Bitcoin Fear & Greed Index shown in every summary |
| **Performance movers** | Best and worst performers across your portfolio by day, week, and month |
| **Buy opportunities** | Tickers currently trading at or below your ceiling, ranked by margin |

---

## Commands

All commands are slash commands — type `/` in Discord to see autocomplete suggestions.

| Command | What it does |
|---------|-------------|
| `/add <TICKER> [wallet\|watchlist]` | Start tracking a ticker (default: watchlist) |
| `/remove <TICKER>` | Stop tracking a ticker and remove its alerts |
| `/tickers` | Show all your tickers with ceiling, alerts, and notes |
| `/alert <TICKER> <PRICE>` | Get a DM when price drops to or below target (fires once) |
| `/ceiling <TICKER> <PRICE>` | Set your personal buy-target price |
| `/ceiling <TICKER> clear` | Remove a ceiling |
| `/ceiling <TICKER>` | Check ceiling vs current price with margin |
| `/note <TICKER> <TEXT>` | Attach a free-text note to a ticker (max 80 characters) |
| `/note <TICKER> clear` | Remove a note |
| `/note <TICKER>` | View the current note |
| `/schedule <HH:MM>` | Schedule a daily summary DM (24h format, uses configured timezone) |
| `/schedule` | View your current schedule |
| `/unschedule` | Cancel your daily summary |
| `/summary` | Get your full portfolio summary right now |
| `/dividends` | Show upcoming dividends for the next 60 days |
| `/refreshcache` | Force-refresh all market data (prices, dividends, Fear & Greed) |
| `/help` | Show all commands |

**Ticker auto-formatting:** `PETR4` → `PETR4.SA` (B3), `BTC` → `BTC-USD` (crypto). US stocks and ETFs like `AAPL` pass through as-is.

---

## What a summary looks like

```
@you Your summary:

# 💼 Wallet
- **BR Stocks**
Ticker  Price      Day%   DY%    Ceiling
─────────────────────────────────────────
PETR4   R$38.10    +1.2%  6.54%  —
VALE3   R$56.40    -0.5%  8.21%  R$60.00 +6%

- **Crypto**
Ticker  Price          Day%
───────────────────────────
BTC     $97,200.00     +3.1%

# 👀 Watchlist
Ticker  Price     Day%
──────────────────────
AAPL    $213.50   +0.8%

# 📊 Market Indicators
Index  Description       Region      Value   Day%   Status
───────────────────────────────────────────────────────────
VIX    Volatility Index  Global      18.5    +2.1%  Moderate
IBOV   Bovespa Index     BR/Stocks   131450  -0.8%  —
F&G    Fear & Greed      Crypto/BTC  65      —      Greed

# 📈 Performance
         Day%            Week%          Month%
  Best:  PETR4 +1.2%     BTC +5.3%      VALE3 +8.4%
  Worst: VALE3 -0.5%     AAPL -1.1%     PETR4 -2.1%

# 📅 Dividends
Ticker  Ex-Date     Pay-Date    Type       Amount
─────────────────────────────────────────────────
PETR4   2026/05/15  2026/05/30  Dividendo  R$1.25
PETR4   2026/05/15  2026/06/10  JCP        R$0.45

# 🛒 Buy Opportunities
Ticker  Price      Ceiling   Margin  In
────────────────────────────────────────
VALE3   R$56.40    R$60.00   +6.4%   wallet
```

---

## Setup

### 1. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, click **Reset Token** and copy it — this is your `DISCORD_TOKEN`.
3. Enable **Message Content Intent** under Privileged Gateway Intents.
4. Under **OAuth2 → URL Generator**, select scope `bot` + `applications.commands` with permissions: Read Messages, Send Messages, Read Message History.
5. Open the generated URL to invite the bot to your server.

### 2. Run with Docker (recommended)

```bash
# Create a .env file with at minimum your bot token
echo "DISCORD_TOKEN=your_token_here" > .env

docker compose up -d
docker compose logs -f
```

### 3. Run locally

```bash
pip install -r requirements.txt

# Create a .env file with at minimum your bot token
echo "DISCORD_TOKEN=your_token_here" > .env

python -m bot.main
```

> Slash commands may take up to 1 hour to appear globally after the first start.

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

All caches are **on-demand only** — data is fetched when a command needs it and stored until the TTL expires. If the bot is idle, no API calls are made. To force an immediate refresh, use `/refreshcache`.

---

## Ticker conventions

| Input | Normalized | Market |
|-------|-----------|--------|
| `PETR4` | `PETR4.SA` | B3 Brazil |
| `BTC` | `BTC-USD` | Crypto |
| `AAPL` | `AAPL` | US stocks / ETFs |

Normalization is automatic — you never need to type `.SA` or `-USD` manually.
