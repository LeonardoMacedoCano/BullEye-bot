import time
import logging

import yfinance as yf

from bot.config import DIV_CACHE_TTL as _DIV_CACHE_TTL
from bot.db.repository import get_price_cache, set_price_cache, upsert_ticker
from bot.services.market import classify_br_subcategory, dividends_trailing_12m
from bot.shared.context import get_request_id

logger = logging.getLogger(__name__)


def get_br_stock_metrics(ticker: str, current_price: float) -> dict:
    upsert_ticker(ticker, classify_br_subcategory(ticker), None)
    row = get_price_cache(ticker)
    stale = row is None or (time.time() - row["updated_at"]) > _DIV_CACHE_TTL

    if stale:
        rid = get_request_id()
        try:
            info = yf.Ticker(ticker).info
            dy_rate = float(info.get("trailingAnnualDividendRate") or 0.0)
            dy_yield = float(info.get("trailingAnnualDividendYield") or 0.0)
        except Exception as exc:
            logger.warning("[%s] Failed to fetch .info for %s: %s", rid, ticker, exc)
            return {"dy_yield": 0.0}

        if dy_rate == 0.0:
            dy_rate = dividends_trailing_12m(ticker)

        set_price_cache(ticker, dy_rate, dy_yield)
    else:
        dy_rate = float(row["dy_rate"] or 0.0)
        dy_yield = float(row["dy_yield"] or 0.0)

    if dy_yield == 0.0 and dy_rate > 0 and current_price > 0:
        dy_yield = dy_rate / current_price

    return {"dy_yield": dy_yield}
