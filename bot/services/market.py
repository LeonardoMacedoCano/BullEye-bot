import logging
import re
import time
import yfinance as yf

logger = logging.getLogger(__name__)

_B3_PATTERN = re.compile(r'^[A-Z]{4,5}(3|4|11)$')
_ALIASES = {"BTC": "BTC-USD"}

SUBCATEGORY_ORDER = ["br-stocks", "crypto", "etf", "stocks"]
SUBCATEGORY_LABELS = {
    "br-stocks": "BR Stocks",
    "crypto": "Crypto",
    "etf": "ETF",
    "stocks": "Stocks",
}


def normalize_ticker(ticker: str) -> str:
    t = ticker.upper().strip()
    if t in _ALIASES:
        return _ALIASES[t]
    if _B3_PATTERN.match(t):
        return f"{t}.SA"
    return t


def get_ticker_data(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        history = t.history(period="1mo")
        if history.empty:
            logger.warning("No data returned for ticker %s (empty history)", ticker)
            return None
        current_price = float(history["Close"].iloc[-1])
        high_30d = float(history["High"].max())
        low_series = history["Low"][history["Low"] > 0]
        low_30d = float(low_series.min()) if not low_series.empty else float(history["Low"].min())
        return {
            "ticker": ticker.upper(),
            "current_price": current_price,
            "high_30d": high_30d,
            "low_30d": low_30d,
        }
    except Exception as exc:
        logger.warning("Failed to fetch data for ticker %s: %s", ticker, exc)
        return None


def validate_ticker(ticker: str) -> bool:
    return get_ticker_data(ticker) is not None


_CACHE_TTL = 86400  # 24h


def _dividends_trailing_12m(ticker: str) -> float:
    try:
        import pandas as pd
        divs = yf.Ticker(ticker).dividends
        if divs.empty:
            return 0.0
        cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
        return float(divs[divs.index >= cutoff].sum())
    except Exception:
        return 0.0


def get_br_stock_metrics(ticker: str, current_price: float) -> dict:
    """
    Returns fundamentals for a BR stock. All ceiling values are float | None.
    {dy_yield, bazin, graham, pe15, pb15}
    Uses ticker_cache (TTL 24h). Re-fetches if stale or if cached dy_rate == 0
    (some B3 tickers have trailingAnnualDividendRate missing in yfinance .info).
    """
    from bot.db.repository import get_ticker_cache, set_ticker_cache

    row = get_ticker_cache(ticker)
    stale = row is None or (time.time() - row["updated_at"]) > _CACHE_TTL
    no_div = row is not None and float(row["dy_rate"] or 0.0) == 0.0

    if stale or no_div:
        try:
            info     = yf.Ticker(ticker).info
            dy_rate  = float(info.get("trailingAnnualDividendRate") or 0.0)
            dy_yield = float(info.get("trailingAnnualDividendYield") or 0.0)
            eps      = float(info.get("trailingEps") or 0.0)
            book_val = float(info.get("bookValue") or 0.0)
        except Exception as exc:
            logger.warning("Failed to fetch .info for %s: %s", ticker, exc)
            return {"dy_yield": 0.0, "bazin": None, "graham": None, "pe15": None, "pb15": None}

        if dy_rate == 0.0:
            dy_rate = _dividends_trailing_12m(ticker)

        set_ticker_cache(ticker, dy_rate, dy_yield, eps, book_val)
    else:
        dy_rate  = float(row["dy_rate"] or 0.0)
        dy_yield = float(row["dy_yield"] or 0.0)
        eps      = float(row["eps"] or 0.0)
        book_val = float(row["book_value"] or 0.0)

    if dy_yield == 0.0 and dy_rate > 0 and current_price > 0:
        dy_yield = dy_rate / current_price

    bazin  = dy_rate / 0.06 if dy_rate > 0 else None
    graham = (22.5 * eps * book_val) ** 0.5 if eps > 0 and book_val > 0 else None
    pe15   = 15.0 * eps if eps > 0 else None
    pb15   = 1.5 * book_val if book_val > 0 else None

    return {"dy_yield": dy_yield, "bazin": bazin, "graham": graham, "pe15": pe15, "pb15": pb15}


def get_ticker_subcategory(ticker: str) -> str | None:
    if ticker.upper().endswith(".SA"):
        return "br-stocks"
    try:
        quote_type = yf.Ticker(ticker).info.get("quoteType", "").upper()
        if quote_type == "CRYPTOCURRENCY":
            return "crypto"
        if quote_type == "ETF":
            return "etf"
        if quote_type == "EQUITY":
            return "stocks"
    except Exception:
        pass
    return None
