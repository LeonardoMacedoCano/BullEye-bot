import logging

from bot.db.repository import get_proventos_upcoming
from bot.services.market import get_ticker_data
from bot.application.market_cache import get_br_stock_metrics, get_dividend_info
from bot.shared.formatting import currency, display_name

logger = logging.getLogger(__name__)


def get_dividends_rows(tickers: list) -> list[dict]:
    for row in tickers:
        ticker = row["ticker"]
        if ticker.upper().endswith(".SA"):
            data = get_ticker_data(ticker)
            if data:
                get_br_stock_metrics(ticker, data["current_price"])
        else:
            get_dividend_info(ticker)

    ticker_names = [row["ticker"] for row in tickers]
    db_rows = get_proventos_upcoming(ticker_names)

    result = []
    for row in db_rows:
        ticker = row["symbol"]
        sym = currency(ticker)
        name = display_name(ticker)
        ex_d = row["ex_date"].replace("-", "/") if row["ex_date"] else "—"
        pay_d = row["pay_date"].replace("-", "/") if row["pay_date"] else "—"
        amount = row["amount"]
        amt_str = f"{sym}{amount:,.2f}" if amount else "—"
        result.append({
            "name": name,
            "ex_date": ex_d,
            "pay_date": pay_d,
            "type": row["type"] or "—",
            "amount": amt_str,
        })
    return result
