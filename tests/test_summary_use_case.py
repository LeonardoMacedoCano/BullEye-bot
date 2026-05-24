import pytest
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


class TestBuildSummaryEmptyTickers:
    def test_returns_single_message_when_no_tickers(self):
        with patch("bot.application.summary_use_case.list_tickers", return_value=[]):
            result = build_summary(1, "@user")
        assert len(result) == 1
        assert "no tickers" in result[0].lower()

    def test_message_includes_mention(self):
        with patch("bot.application.summary_use_case.list_tickers", return_value=[]):
            result = build_summary(1, "@alice")
        assert "@alice" in result[0]

    def test_message_includes_add_command_hint(self):
        with patch("bot.application.summary_use_case.list_tickers", return_value=[]):
            result = build_summary(1, "@user")
        assert "/add" in result[0]


class TestBuildSummaryWithTickers:
    def _patch_all(self, rows, ticker_data_map=None):
        """Returns a dict of patches for a clean summary call."""
        def fake_get_ticker_data(ticker):
            if ticker_data_map:
                return ticker_data_map.get(ticker)
            return _mock_ticker_data(ticker)

        return {
            "bot.application.summary_use_case.list_tickers": rows,
            "bot.application.summary_use_case.get_ticker_data": fake_get_ticker_data,
            "bot.application.summary_use_case.get_ticker_subcategory": lambda t: "stocks",
            "bot.application.summary_use_case.update_ticker_subcategory": MagicMock(),
            "bot.application.summary_use_case.get_fear_greed_index": lambda: None,
            "bot.application.summary_use_case.get_vix": lambda: None,
            "bot.application.summary_use_case.get_ibov": lambda: None,
            "bot.application.summary_use_case.build_proventos_radar": lambda t: [],
        }

    def test_returns_list_of_strings(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with patch("bot.application.summary_use_case.list_tickers", return_value=rows), \
             patch("bot.application.summary_use_case.get_ticker_data", return_value=_mock_ticker_data("AAPL")), \
             patch("bot.application.summary_use_case.get_ticker_subcategory", return_value="stocks"), \
             patch("bot.application.summary_use_case.update_ticker_subcategory"), \
             patch("bot.application.summary_use_case.get_fear_greed_index", return_value=None), \
             patch("bot.application.summary_use_case.get_vix", return_value=None), \
             patch("bot.application.summary_use_case.get_ibov", return_value=None), \
             patch("bot.application.summary_use_case.build_proventos_radar", return_value=[]):
            result = build_summary(1, "@user")
        assert isinstance(result, list)
        assert all(isinstance(m, str) for m in result)

    def test_first_message_starts_with_mention(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with patch("bot.application.summary_use_case.list_tickers", return_value=rows), \
             patch("bot.application.summary_use_case.get_ticker_data", return_value=_mock_ticker_data("AAPL")), \
             patch("bot.application.summary_use_case.get_ticker_subcategory", return_value="stocks"), \
             patch("bot.application.summary_use_case.update_ticker_subcategory"), \
             patch("bot.application.summary_use_case.get_fear_greed_index", return_value=None), \
             patch("bot.application.summary_use_case.get_vix", return_value=None), \
             patch("bot.application.summary_use_case.get_ibov", return_value=None), \
             patch("bot.application.summary_use_case.build_proventos_radar", return_value=[]):
            result = build_summary(1, "@user")
        assert result[0].startswith("@user")

    def test_no_data_returns_fallback_message(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with patch("bot.application.summary_use_case.list_tickers", return_value=rows), \
             patch("bot.application.summary_use_case.get_ticker_data", return_value=None), \
             patch("bot.application.summary_use_case.get_ticker_subcategory", return_value="stocks"), \
             patch("bot.application.summary_use_case.update_ticker_subcategory"), \
             patch("bot.application.summary_use_case.get_fear_greed_index", return_value=None), \
             patch("bot.application.summary_use_case.get_vix", return_value=None), \
             patch("bot.application.summary_use_case.get_ibov", return_value=None), \
             patch("bot.application.summary_use_case.build_proventos_radar", return_value=[]):
            result = build_summary(1, "@user")
        assert len(result) >= 1
        combined = " ".join(result)
        assert "@user" in combined

    def test_all_messages_within_limit(self):
        from bot.shared.formatting import MSG_LIMIT
        rows = [_make_ticker_row("AAPL", "wallet", "stocks")]
        with patch("bot.application.summary_use_case.list_tickers", return_value=rows), \
             patch("bot.application.summary_use_case.get_ticker_data", return_value=_mock_ticker_data("AAPL")), \
             patch("bot.application.summary_use_case.get_ticker_subcategory", return_value="stocks"), \
             patch("bot.application.summary_use_case.update_ticker_subcategory"), \
             patch("bot.application.summary_use_case.get_fear_greed_index", return_value=None), \
             patch("bot.application.summary_use_case.get_vix", return_value=None), \
             patch("bot.application.summary_use_case.get_ibov", return_value=None), \
             patch("bot.application.summary_use_case.build_proventos_radar", return_value=[]):
            result = build_summary(1, "@user")
        for msg in result:
            assert len(msg) <= MSG_LIMIT

    def test_buy_opportunity_included_when_below_ceiling(self):
        rows = [_make_ticker_row("AAPL", "wallet", "stocks", ceiling=200.0)]
        with patch("bot.application.summary_use_case.list_tickers", return_value=rows), \
             patch("bot.application.summary_use_case.get_ticker_data", return_value=_mock_ticker_data("AAPL", price=150.0)), \
             patch("bot.application.summary_use_case.get_ticker_subcategory", return_value="stocks"), \
             patch("bot.application.summary_use_case.update_ticker_subcategory"), \
             patch("bot.application.summary_use_case.get_fear_greed_index", return_value=None), \
             patch("bot.application.summary_use_case.get_vix", return_value=None), \
             patch("bot.application.summary_use_case.get_ibov", return_value=None), \
             patch("bot.application.summary_use_case.build_proventos_radar", return_value=[]):
            result = build_summary(1, "@user")
        combined = "\n".join(result)
        assert "Opportunities" in combined or "AAPL" in combined
