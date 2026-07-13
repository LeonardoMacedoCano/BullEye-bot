from unittest.mock import patch, MagicMock
from bot.application.summary_use_case import build_summary


def _make_ticker_row(ticker, category="wallet", subcategory="stocks", ceiling=None):
    """Creates a dict-like row that mimics sqlite3.Row for testing."""
    return {
        "ticker": ticker,
        "category": category,
        "subcategory": subcategory,
        "user_ceiling": ceiling,
        "note": None,
        "alert_price": None,
    }


def _mock_ticker_data(ticker, price=100.0):
    return {
        "ticker": ticker,
        "current_price": price,
        "day_change_pct": 0.5,
        "week_change_pct": 1.0,
        "month_change_pct": 2.0,
        "high_30d": price * 1.1,
        "low_30d": price * 0.9,
    }


def _patched(rows, ticker_data_map=None, fg=None, fgi_ceiling=None, dividends=None):
    def fake_get_ticker_data(ticker):
        if ticker_data_map is not None:
            return ticker_data_map.get(ticker)
        return _mock_ticker_data(ticker)

    return patch.multiple(
        "bot.application.summary_use_case",
        list_tickers=MagicMock(return_value=rows),
        get_ticker_data=MagicMock(side_effect=fake_get_ticker_data),
        get_ticker_subcategory=MagicMock(return_value="stocks"),
        update_ticker_subcategory=MagicMock(),
        get_fear_greed_index=MagicMock(return_value=fg),
        get_user_fgi_ceiling=MagicMock(return_value=fgi_ceiling),
        get_vix=MagicMock(return_value=None),
        get_ibov=MagicMock(return_value=None),
        get_dividends_rows=MagicMock(return_value=dividends or []),
    )


class TestBuildSummaryEmptyTickers:
    def test_returns_empty_result_when_no_tickers(self):
        with patch("bot.application.summary_use_case.list_tickers", return_value=[]):
            result = build_summary(1, "@user")
        assert result == {"empty": True, "mention": "@user"}


class TestBuildSummaryWithTickers:
    def test_returns_dict_with_expected_keys(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with _patched(rows):
            result = build_summary(1, "@user")
        assert result["empty"] is False
        assert result["mention"] == "@user"
        assert set(result) == {
            "empty", "mention", "wallet_groups", "watchlist_groups",
            "avg_day_change", "market", "performance", "dividends", "opportunities",
        }

    def test_wallet_ticker_appears_in_wallet_groups(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with _patched(rows):
            result = build_summary(1, "@user")
        assert len(result["wallet_groups"]) == 1
        assert "AAPL" in result["wallet_groups"][0]["table_str"]
        assert result["watchlist_groups"] == []

    def test_no_market_data_does_not_crash(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with _patched(rows, ticker_data_map={}):
            result = build_summary(1, "@user")
        assert result["empty"] is False
        assert result["avg_day_change"] is None

    def test_buy_opportunity_included_when_below_ceiling(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks", ceiling=200.0)]
        with _patched(rows, ticker_data_map={"AAPL": _mock_ticker_data("AAPL", price=150.0)}):
            result = build_summary(1, "@user")
        opps = result["opportunities"]["ticker_opps"]
        assert len(opps) == 1
        assert opps[0]["name"] == "AAPL"
        assert opps[0]["margin"] == "+33.3%"

    def test_no_opportunity_when_above_ceiling(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks", ceiling=100.0)]
        with _patched(rows, ticker_data_map={"AAPL": _mock_ticker_data("AAPL", price=150.0)}):
            result = build_summary(1, "@user")
        assert result["opportunities"]["ticker_opps"] == []

    def test_fgi_ceiling_included_in_market_data(self):
        rows = [_make_ticker_row("BTC-USD", "wallet", "crypto")]
        fg_data = {"value": 30, "classification": "Fear"}
        with _patched(
            rows,
            ticker_data_map={"BTC-USD": _mock_ticker_data("BTC-USD")},
            fg=fg_data,
            fgi_ceiling=45,
        ):
            result = build_summary(1, "@user")
        assert result["market"]["fgi"]["value"] == 30
        assert result["market"]["fgi"]["fgi_ceiling"] == 45

    def test_fgi_opportunity_triggered_when_below_ceiling(self):
        rows = [_make_ticker_row("BTC-USD", "wallet", "crypto")]
        fg_data = {"value": 20, "classification": "Extreme Fear"}
        with _patched(
            rows,
            ticker_data_map={"BTC-USD": _mock_ticker_data("BTC-USD")},
            fg=fg_data,
            fgi_ceiling=45,
        ):
            result = build_summary(1, "@user")
        opps = result["opportunities"]
        assert opps["fgi_triggered"] is True
        assert opps["fgi_data"] == {"value": 20, "ceiling": 45, "classification": "Extreme Fear"}

    def test_fgi_opportunity_not_triggered_when_above_ceiling(self):
        rows = [_make_ticker_row("BTC-USD", "wallet", "crypto")]
        fg_data = {"value": 70, "classification": "Greed"}
        with _patched(
            rows,
            ticker_data_map={"BTC-USD": _mock_ticker_data("BTC-USD")},
            fg=fg_data,
            fgi_ceiling=45,
        ):
            result = build_summary(1, "@user")
        assert result["opportunities"]["fgi_triggered"] is False

    def test_dividends_rows_passed_through(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        fake_dividends = [
            {"name": "AAPL", "ex_date": "01/01", "pay_date": "02/01", "type": "Dividend", "amount": "$1.00"}
        ]
        with _patched(rows, dividends=fake_dividends):
            result = build_summary(1, "@user")
        assert result["dividends"] == fake_dividends
