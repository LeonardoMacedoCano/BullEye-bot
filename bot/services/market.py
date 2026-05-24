import datetime
import logging
import re
import threading
import time
from collections import OrderedDict

import requests
import yfinance as yf

from bot.shared.context import get_request_id

logger = logging.getLogger(__name__)

_cache_stats = {"hits": 0, "misses": 0, "errors": 0}
_cache_stats_lock = threading.Lock()


def get_cache_stats() -> dict:
    with _cache_stats_lock:
        return dict(_cache_stats)

_B3_PATTERN = re.compile(r'^[A-Z]{4,5}(3|4|11)$')
_ALIASES = {"BTC": "BTC-USD"}

SUBCATEGORY_ORDER = ["br-stocks", "crypto", "etf", "stocks"]
SUBCATEGORY_LABELS = {
    "br-stocks": "BR Stocks",
    "crypto": "Crypto",
    "etf": "ETF",
    "stocks": "Stocks",
}

_BR_TYPE_MAP = {
    "DIVIDENDO": "Dividendo",
    "JCP": "JSCP",
    "RENDIMENTO": "Rendimento",
    "SUBSCRICAO": "Subscrição",
}

from bot.config import PRICE_CACHE_TTL as _PRICE_CACHE_TTL

_PRICE_CACHE_MAX = 500
_price_cache: OrderedDict[str, tuple[dict, float]] = OrderedDict()
_price_cache_lock = threading.Lock()


def ts_to_date(ts) -> str | None:
    if not ts:
        return None
    try:
        return datetime.date.fromtimestamp(int(ts)).isoformat()
    except Exception:
        return None


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
    rid = get_request_id()
    now = time.time()
    with _price_cache_lock:
        cached = _price_cache.get(ticker)
        if cached is not None and now - cached[1] < _PRICE_CACHE_TTL:
            with _cache_stats_lock:
                _cache_stats["hits"] += 1
            logger.debug("[%s] Cache hit for %s", rid, ticker)
            return cached[0]
    with _cache_stats_lock:
        _cache_stats["misses"] += 1
    try:
        t = yf.Ticker(ticker)
        history = t.history(period="1mo")
        if history.empty:
            logger.warning("[%s] No data returned for ticker %s (empty history)", rid, ticker)
            with _cache_stats_lock:
                _cache_stats["errors"] += 1
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
            if ticker in _price_cache:
                _price_cache.move_to_end(ticker)
            _price_cache[ticker] = (data, now)
            if len(_price_cache) > _PRICE_CACHE_MAX:
                _price_cache.popitem(last=False)
        return data
    except Exception as exc:
        logger.warning("[%s] Failed to fetch data for ticker %s: %s", rid, ticker, exc)
        with _cache_stats_lock:
            _cache_stats["errors"] += 1
        return None


def validate_ticker(ticker: str) -> bool:
    return get_ticker_data(ticker) is not None


def dividends_trailing_12m(ticker: str) -> float:
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


def fetch_br_proventos(ticker: str) -> list[dict]:
    """Fetches proventos from brapi.dev. Returns list of dicts; caller handles DB writes."""
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
            return []
        proventos = []
        for div in results[0].get("dividendsData", {}).get("cashDividends", []):
            ex_date = (div.get("lastDatePrior") or "")[:10]
            if not ex_date:
                continue
            pay_date = (div.get("paymentDate") or "")[:10] or None
            amount = float(div.get("rate") or 0.0) or None
            raw_type = (div.get("paymentType") or "").upper()
            ptype = _BR_TYPE_MAP.get(raw_type, raw_type or "Dividendo")
            description = div.get("label") or None
            proventos.append({
                "ex_date": ex_date,
                "pay_date": pay_date,
                "amount": amount,
                "type": ptype,
                "description": description,
            })
        return proventos
    except Exception as exc:
        logger.debug("brapi proventos fetch failed for %s: %s", ticker, exc)
        return []


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
