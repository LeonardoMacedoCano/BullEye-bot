import logging
import re
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
