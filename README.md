# BullEyeBot

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Self-hosted](https://img.shields.io/badge/deployment-self--hosted-lightgrey)

> Your personal financial market assistant on Discord. Track stocks, crypto, and ETFs — get price alerts, dividend radars, and daily summaries without leaving your server.

Supports Brazilian B3 stocks, US equities, ETFs, and cryptocurrencies. Pulls live data from [yfinance](https://github.com/ranaroussi/yfinance) and [brapi.dev](https://brapi.dev), with a local cache to keep responses fast and API calls low.

**This is a self-hosted bot** — there's no public invite link. You run your own instance (a few minutes with Docker, see below) and it lives on your server only. Each user of that server gets their own isolated tickers, alerts, and schedule.

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
| **Fear & Greed ceiling/alert** | Set a personal Fear & Greed Index threshold — see it flagged in `/summary`, or get a one-time DM when it's reached |
| **Performance movers** | Best and worst performers across your portfolio by day, week, and month |
| **Buy opportunities** | Tickers currently trading at or below your ceiling, ranked by margin |

Full list of slash commands → **[docs/COMMANDS.md](docs/COMMANDS.md)**

---

## What a summary looks like

`/summary` sends two Discord embeds:

**📊 Portfolio** — one field per group (Wallet / Watchlist, split further by subcategory when you hold BR stocks, crypto, ETFs, etc.), each a compact price table with day change color-coded green/red:

```
Ticker  Price      Day%   DY%    Ceiling
─────────────────────────────────────────
PETR4   R$38.10    +1.2%  6.54%  —
VALE3   R$56.40    -0.5%  8.21%  R$60.00 +6%
```

**📈 Market Intelligence** — VIX/IBOV/Fear & Greed indicators, best & worst performers by day/week/month, upcoming dividends, and buy opportunities (tickers at or below your ceiling), each as its own field.

---

## Quick start

```bash
git clone https://github.com/LeonardoMacedoCano/BullEye-bot.git
cd BullEye-bot
echo "DISCORD_TOKEN=your_token_here" > .env
docker compose up -d
```

Need a bot token, or want to run it without Docker? Full walkthrough (creating the Discord app, environment variables, running tests) → **[docs/SETUP.md](docs/SETUP.md)**

---

## Built with

discord.py · SQLite · [yfinance](https://github.com/ranaroussi/yfinance) · [brapi.dev](https://brapi.dev)

Want to see how it's structured under the hood (architecture, layering, coding conventions)? See **[CLAUDE.md](CLAUDE.md)**.

## License

[MIT](LICENSE) — do what you want with it, just keep the copyright notice.
