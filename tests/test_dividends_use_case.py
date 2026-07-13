from unittest.mock import patch, MagicMock
from bot.application.dividends_use_case import get_dividends_rows


def _make_ticker_row(ticker):
    return {"ticker": ticker}


def _make_provento_row(symbol, ex_date="2026-08-01", pay_date="2026-08-15", amount=1.5, ptype="Dividend"):
    return {"symbol": symbol, "ex_date": ex_date, "pay_date": pay_date, "amount": amount, "type": ptype}


class TestGetDividendsRows:
    def test_returns_empty_list_when_no_upcoming_dividends(self):
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value=None), \
             patch("bot.application.dividends_use_case.get_dividend_info"), \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=[]):
            result = get_dividends_rows([_make_ticker_row("AAPL")])
        assert result == []

    def test_formats_br_ticker_row(self):
        rows = [_make_provento_row("PETR4.SA", amount=2.5)]
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value={"current_price": 30.0}), \
             patch("bot.application.dividends_use_case.get_br_stock_metrics"), \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=rows):
            result = get_dividends_rows([_make_ticker_row("PETR4.SA")])
        assert result == [{
            "name": "PETR4",
            "ex_date": "2026/08/01",
            "pay_date": "2026/08/15",
            "type": "Dividend",
            "amount": "R$2.50",
        }]

    def test_formats_us_ticker_row_with_dollar_symbol(self):
        rows = [_make_provento_row("AAPL", amount=0.24, ptype="Dividend")]
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value=None), \
             patch("bot.application.dividends_use_case.get_dividend_info"), \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=rows):
            result = get_dividends_rows([_make_ticker_row("AAPL")])
        assert result[0]["name"] == "AAPL"
        assert result[0]["amount"] == "$0.24"

    def test_missing_amount_renders_as_dash(self):
        rows = [_make_provento_row("AAPL", amount=None)]
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value=None), \
             patch("bot.application.dividends_use_case.get_dividend_info"), \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=rows):
            result = get_dividends_rows([_make_ticker_row("AAPL")])
        assert result[0]["amount"] == "—"

    def test_missing_dates_render_as_dash(self):
        rows = [_make_provento_row("AAPL", ex_date=None, pay_date=None)]
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value=None), \
             patch("bot.application.dividends_use_case.get_dividend_info"), \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=rows):
            result = get_dividends_rows([_make_ticker_row("AAPL")])
        assert result[0]["ex_date"] == "—"
        assert result[0]["pay_date"] == "—"

    def test_primes_cache_for_each_ticker_before_querying_db(self):
        br_data = MagicMock(get_ticker_data=MagicMock(return_value={"current_price": 10.0}))
        with patch("bot.application.dividends_use_case.get_ticker_data", return_value={"current_price": 10.0}) as gtd, \
             patch("bot.application.dividends_use_case.get_br_stock_metrics") as brm, \
             patch("bot.application.dividends_use_case.get_dividend_info") as gdi, \
             patch("bot.application.dividends_use_case.get_proventos_upcoming", return_value=[]) as gpu:
            get_dividends_rows([_make_ticker_row("PETR4.SA"), _make_ticker_row("AAPL")])
        gtd.assert_called_once_with("PETR4.SA")
        brm.assert_called_once_with("PETR4.SA", 10.0)
        gdi.assert_called_once_with("AAPL")
        gpu.assert_called_once_with(["PETR4.SA", "AAPL"])
