import time
import logging

import yfinance as yf

from bot.config import DIV_CACHE_TTL as _DIV_CACHE_TTL
from bot.db.repository import (
    get_price_cache, set_price_cache, upsert_ticker,
    upsert_provento, get_proventos_for_ticker,
)
from bot.services.market import dividends_trailing_12m, fetch_br_proventos, ts_to_date
from bot.shared.context import get_request_id

logger = logging.getLogger(__name__)


def get_br_stock_metrics(ticker: str, current_price: float) -> dict:
    ticker_id = upsert_ticker(ticker, "br-stocks", None)
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

        for prov in fetch_br_proventos(ticker):
            upsert_provento(
                ticker_id,
                prov["ex_date"], prov["pay_date"],
                prov["amount"], prov["type"], prov["description"],
            )

        if not get_proventos_for_ticker(ticker_id):
            ex_div = ts_to_date(info.get("exDividendDate"))
            div_amount = float(info.get("dividendRate") or dy_rate or 0.0)
            if ex_div:
                upsert_provento(
                    ticker_id, ex_div, None,
                    div_amount if div_amount > 0 else None,
                    "Dividendo", None,
                )
    else:
        dy_rate = float(row["dy_rate"] or 0.0)
        dy_yield = float(row["dy_yield"] or 0.0)

    if dy_yield == 0.0 and dy_rate > 0 and current_price > 0:
        dy_yield = dy_rate / current_price

    return {"dy_yield": dy_yield}


def get_dividend_info(ticker: str) -> dict | None:
    ticker_id = upsert_ticker(ticker, None, None)
    row = get_price_cache(ticker)
    stale = row is None or (time.time() - row["updated_at"]) > _DIV_CACHE_TTL

    if stale:
        try:
            info = yf.Ticker(ticker).info
            dy_rate = float(info.get("trailingAnnualDividendRate") or 0.0)
            dy_yield = float(info.get("trailingAnnualDividendYield") or 0.0)
            ex_div_date = ts_to_date(info.get("exDividendDate"))
            pay_date_str = ts_to_date(info.get("payDate") or info.get("dividendDate"))
            div_amount = float(info.get("dividendRate") or dy_rate or 0.0)
            set_price_cache(ticker, dy_rate, dy_yield)
            if ex_div_date:
                upsert_provento(
                    ticker_id, ex_div_date, pay_date_str,
                    div_amount if div_amount > 0 else None,
                    "Dividendo", None,
                )
        except Exception as exc:
            logger.warning("[%s] Failed to fetch dividend info for %s: %s", get_request_id(), ticker, exc)
            return None

    return {}
