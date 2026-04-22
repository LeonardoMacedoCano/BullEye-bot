import logging
import yfinance as yf

logger = logging.getLogger(__name__)


def get_ticker_data(ticker: str) -> dict | None:
    try:
        t = yf.Ticker(ticker)
        history = t.history(period="30d")
        if history.empty:
            logger.warning("No data returned for ticker: %s", ticker)
            return None
        current_price = float(history["Close"].iloc[-1])
        high_30d = float(history["High"].max())
        low_30d = float(history["Low"].min())
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
