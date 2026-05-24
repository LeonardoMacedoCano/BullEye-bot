import logging

from bot.db.repository import get_proventos_upcoming
from bot.services.market import get_ticker_data
from bot.application.market_cache import get_br_stock_metrics, get_dividend_info
from bot.shared.formatting import currency, display_name, render_table, MSG_LIMIT

logger = logging.getLogger(__name__)


def build_proventos_radar(tickers: list) -> list[str]:
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
    if not db_rows:
        return []

    def _fmt_date(d: str | None) -> str:
        return d.replace("-", "/") if d else "—"

    headers = ["Ticker", "Ex-Date", "Pay-Date", "Type", "Amount"]
    data_rows: list[list[str]] = []
    for row in db_rows:
        ticker = row["symbol"]
        sym = currency(ticker)
        name = display_name(ticker)
        ex_d = _fmt_date(row["ex_date"])
        pay_d = _fmt_date(row["pay_date"])
        ptype = row["type"] or "—"
        amount = row["amount"]
        amt_str = f"{sym}{amount:,.2f}" if amount else "—"
        data_rows.append([name, ex_d, pay_d, ptype, amt_str])

    table_str = render_table(headers, data_rows, required_headers=["Pay-Date", "Type"])
    if not table_str:
        return []
    msg = f"# 📅 Dividends\n```\n{table_str}\n```"
    return [msg] if len(msg) <= MSG_LIMIT else [msg[:MSG_LIMIT]]
