import logging
import re
import threading
import time
import requests
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

from bot.config import PRICE_CACHE_TTL as _PRICE_CACHE_TTL, DIV_CACHE_TTL as _DIV_CACHE_TTL

_price_cache: dict[str, tuple[dict, float]] = {}
_price_cache_lock = threading.Lock()

_BR_TYPE_MAP = {
    "DIVIDENDO": "Dividendo",
    "JCP": "JSCP",
    "RENDIMENTO": "Rendimento",
    "SUBSCRICAO": "Subscrição",
}


def _ts_to_date(ts) -> str | None:
    if not ts:
        return None
    try:
        import datetime
        return datetime.date.fromtimestamp(int(ts)).isoformat()
    except Exception:
        return None


def _fetch_br_proventos(ticker: str, ticker_id: int) -> None:
    from bot.db.repository import upsert_provento
    symbol = ticker.upper().replace(".SA", "")
    try:
        resp = requests.get(
            f"https://brapi.dev/api/quote/{symbol}",
            params={"modules": "dividendsData"},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return
        for div in results[0].get("dividendsData", {}).get("cashDividends", []):
            ex_date = (div.get("lastDatePrior") or "")[:10]
            if not ex_date:
                continue
            pay_date = (div.get("paymentDate") or "")[:10] or None
            amount = float(div.get("rate") or 0.0) or None
            raw_type = (div.get("paymentType") or "").upper()
            ptype = _BR_TYPE_MAP.get(raw_type, raw_type or "Dividendo")
            description = div.get("label") or None
            upsert_provento(ticker_id, ex_date, pay_date, amount, ptype, description)
    except Exception as exc:
        logger.debug("brapi proventos fetch failed for %s: %s", ticker, exc)


def clear_price_cache() -> int:
    with _price_cache_lock:
        count = len(_price_cache)
        _price_cache.clear()
    return count


def normalize_ticker(ticker: str) -> str:
    t = ticker.upper().strip()
    if t in _ALIASES:
        return _ALIASES[t]
    if _B3_PATTERN.match(t):
        return f"{t}.SA"
    return t


def get_ticker_data(ticker: str) -> dict | None:
    now = time.time()
    with _price_cache_lock:
        cached = _price_cache.get(ticker)
        if cached is not None and now - cached[1] < _PRICE_CACHE_TTL:
            return cached[0]
    try:
        t = yf.Ticker(ticker)
        history = t.history(period="1mo")
        if history.empty:
            logger.warning("No data returned for ticker %s (empty history)", ticker)
            return None
        close = history["Close"]
        current_price = float(close.iloc[-1])
        high_30d = float(history["High"].max())
        low_series = history["Low"][history["Low"] > 0]
        low_30d = float(low_series.min()) if not low_series.empty else float(history["Low"].min())
        n = len(close)
        day_change_pct   = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] * 100) if n >= 2 else 0.0
        week_change_pct  = float((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100) if n >= 6 else day_change_pct
        month_change_pct = float((close.iloc[-1] - close.iloc[0])  / close.iloc[0]  * 100) if n >= 2 else 0.0
        data = {
            "ticker": ticker.upper(),
            "current_price": current_price,
            "high_30d": high_30d,
            "low_30d": low_30d,
            "day_change_pct": day_change_pct,
            "week_change_pct": week_change_pct,
            "month_change_pct": month_change_pct,
        }
        with _price_cache_lock:
            _price_cache[ticker] = (data, now)
        return data
    except Exception as exc:
        logger.warning("Failed to fetch data for ticker %s: %s", ticker, exc)
        return None


def validate_ticker(ticker: str) -> bool:
    return get_ticker_data(ticker) is not None


def _dividends_trailing_12m(ticker: str) -> float:
    try:
        import pandas as pd
        divs = yf.Ticker(ticker).dividends
        if divs.empty:
            return 0.0
        cutoff = pd.Timestamp.now(tz=divs.index.tz) - pd.Timedelta(days=365)
        return float(divs[divs.index >= cutoff].sum())
    except Exception as exc:
        logger.warning("Failed to fetch dividends for %s: %s", ticker, exc)
        return 0.0


def get_br_stock_metrics(ticker: str, current_price: float) -> dict:
    from bot.db.repository import get_price_cache, set_price_cache, upsert_ticker, upsert_provento

    ticker_id = upsert_ticker(ticker, "br-stocks", None)
    row = get_price_cache(ticker)
    stale = row is None or (time.time() - row["updated_at"]) > _DIV_CACHE_TTL

    if stale:
        try:
            info     = yf.Ticker(ticker).info
            dy_rate  = float(info.get("trailingAnnualDividendRate") or 0.0)
            dy_yield = float(info.get("trailingAnnualDividendYield") or 0.0)
        except Exception as exc:
            logger.warning("Failed to fetch .info for %s: %s", ticker, exc)
            return {"dy_yield": 0.0}

        if dy_rate == 0.0:
            dy_rate = _dividends_trailing_12m(ticker)

        set_price_cache(ticker, dy_rate, dy_yield)
        _fetch_br_proventos(ticker, ticker_id)

        from bot.db.repository import get_proventos_for_ticker
        if not get_proventos_for_ticker(ticker_id):
            ex_div = _ts_to_date(info.get("exDividendDate"))
            div_amount = float(info.get("dividendRate") or dy_rate or 0.0)
            if ex_div:
                upsert_provento(
                    ticker_id, ex_div, None,
                    div_amount if div_amount > 0 else None,
                    "Dividendo", None,
                )
    else:
        dy_rate  = float(row["dy_rate"] or 0.0)
        dy_yield = float(row["dy_yield"] or 0.0)

    if dy_yield == 0.0 and dy_rate > 0 and current_price > 0:
        dy_yield = dy_rate / current_price

    return {"dy_yield": dy_yield}


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


def get_dividend_info(ticker: str) -> dict | None:
    from bot.db.repository import get_price_cache, set_price_cache, upsert_ticker, upsert_provento

    ticker_id = upsert_ticker(ticker, None, None)
    row = get_price_cache(ticker)
    stale = row is None or (time.time() - row["updated_at"]) > _DIV_CACHE_TTL

    if stale:
        try:
            info         = yf.Ticker(ticker).info
            dy_rate      = float(info.get("trailingAnnualDividendRate") or 0.0)
            dy_yield     = float(info.get("trailingAnnualDividendYield") or 0.0)
            ex_div_date  = _ts_to_date(info.get("exDividendDate"))
            pay_date_str = _ts_to_date(info.get("payDate") or info.get("dividendDate"))
            div_amount   = float(info.get("dividendRate") or dy_rate or 0.0)
            set_price_cache(ticker, dy_rate, dy_yield)
            if ex_div_date:
                upsert_provento(
                    ticker_id, ex_div_date, pay_date_str,
                    div_amount if div_amount > 0 else None,
                    "Dividendo", None,
                )
        except Exception as exc:
            logger.warning("Failed to fetch dividend info for %s: %s", ticker, exc)
            return None

    return {}
