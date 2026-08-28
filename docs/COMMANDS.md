# Commands

[← Back to README](../README.md)

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
| `/ceiling_fear_greed <1-100>` | Set your personal Crypto Fear & Greed Index ceiling |
| `/ceiling_fear_greed clear` | Remove the Fear & Greed ceiling |
| `/ceiling_fear_greed` | Check the Fear & Greed Index vs your ceiling |
| `/alert_fear_greed <1-100>` | Get a DM when the Fear & Greed Index reaches or drops below target (fires once) |
| `/note <TICKER> <TEXT>` | Attach a free-text note to a ticker (max 80 characters) |
| `/note <TICKER> clear` | Remove a note |
| `/note <TICKER>` | View the current note |
| `/schedule <HH:MM>` | Schedule a daily summary DM (24h format, uses configured timezone) |
| `/schedule` | View your current schedule |
| `/unschedule` | Cancel your daily summary |
| `/summary` | Get your full portfolio summary right now |
| `/dividends` | Show upcoming dividends for the next 60 days |
| `/refreshcache` | Force-refresh your own market data (prices, dividends, Fear & Greed) |
| `/help` | Show all commands |

`/dividends`, `/tickers`, `/help`, and `/refreshcache` render as embeds; other commands (`/alert`, `/ceiling`, `/note`, `/schedule`, etc.) reply with a plain one-line confirmation.

---

## Ticker conventions

| Input | Normalized | Market |
|-------|-----------|--------|
| `PETR4` | `PETR4.SA` | B3 Brazil |
| `BTC` | `BTC-USD` | Crypto |
| `AAPL` | `AAPL` | US stocks / ETFs |

Normalization is automatic — you never need to type `.SA` or `-USD` manually.
