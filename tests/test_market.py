import datetime
import logging

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch
import bot.services.market as market
from bot.services.market import (
    normalize_ticker, ts_to_date, get_ticker_metadata, get_ticker_subcategory,
    clear_price_cache_for, get_ticker_data, fetch_br_proventos,
)

_TZ = datetime.timezone(datetime.timedelta(hours=-3))


def _history_df(closes: list[float], end: pd.Timestamp) -> pd.DataFrame:
    idx = pd.date_range(end=end, periods=len(closes), freq="D", tz=_TZ)
    closes = np.array(closes, dtype=float)
    return pd.DataFrame(
        {"Close": closes, "High": closes + 1, "Low": closes - 1},
        index=idx,
    )


class TestNormalizeTicker:
    def test_btc_alias(self):
        assert normalize_ticker("BTC") == "BTC-USD"

    def test_btc_lowercase(self):
        assert normalize_ticker("btc") == "BTC-USD"

    def test_b3_four_char_suffix_3(self):
        assert normalize_ticker("VALE3") == "VALE3.SA"

    def test_b3_four_char_suffix_4(self):
        assert normalize_ticker("PETR4") == "PETR4.SA"

    def test_b3_five_char_suffix_11(self):
        assert normalize_ticker("BOVA11") == "BOVA11.SA"

    def test_us_stock_unchanged(self):
        assert normalize_ticker("AAPL") == "AAPL"

    def test_etf_unchanged(self):
        assert normalize_ticker("SPY") == "SPY"

    def test_already_normalized_b3_unchanged(self):
        assert normalize_ticker("PETR4.SA") == "PETR4.SA"

    def test_strips_leading_trailing_whitespace(self):
        assert normalize_ticker("  AAPL  ") == "AAPL"

    def test_lowercase_b3_normalized(self):
        assert normalize_ticker("petr4") == "PETR4.SA"

    def test_two_letter_ticker_not_b3(self):
        assert normalize_ticker("GE") == "GE"

    def test_six_letter_ticker_not_b3(self):
        assert normalize_ticker("GOOGL") == "GOOGL"


class TestTsToDate:
    def test_none_input_returns_none(self):
        assert ts_to_date(None) is None

    def test_invalid_string_returns_none(self):
        assert ts_to_date("not-a-timestamp") is None

    def test_valid_unix_timestamp(self):
        result = ts_to_date(1700000000)
        assert result is not None
        assert len(result) == 10
        assert result[4] == "-" and result[7] == "-"

    def test_returns_iso_format(self):
        result = ts_to_date(1700000000)
        parts = result.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4  # year
        assert len(parts[1]) == 2  # month
        assert len(parts[2]) == 2  # day


class TestGetTickerMetadata:
    def _mock_yf(self, info: dict):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = info
            yield mock_yf

    def test_br_stock_subcategory_set_from_suffix(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "EQUITY", "sector": "Energy", "industry": "Oil & Gas Integrated"}
            result = get_ticker_metadata("PETR4.SA")
        assert result["subcategory"] == "br-stocks"

    def test_br_stock_fetches_sector_and_industry(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "EQUITY", "sector": "Energy", "industry": "Oil & Gas Integrated"}
            result = get_ticker_metadata("PETR4.SA")
        assert result["sector"] == "Energy"
        assert result["industry"] == "Oil & Gas Integrated"

    def test_crypto_subcategory(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "CRYPTOCURRENCY"}
            result = get_ticker_metadata("BTC-USD")
        assert result["subcategory"] == "crypto"
        assert result["sector"] is None
        assert result["industry"] is None

    def test_etf_subcategory(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "ETF"}
            result = get_ticker_metadata("SPY")
        assert result["subcategory"] == "etf"

    def test_equity_subcategory_and_metadata(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {
                "quoteType": "EQUITY",
                "sector": "Technology",
                "industry": "Consumer Electronics",
            }
            result = get_ticker_metadata("AAPL")
        assert result["subcategory"] == "stocks"
        assert result["sector"] == "Technology"
        assert result["industry"] == "Consumer Electronics"

    def test_missing_sector_returns_none(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "EQUITY"}
            result = get_ticker_metadata("AAPL")
        assert result["sector"] is None
        assert result["industry"] is None

    def test_empty_string_sector_coerced_to_none(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "EQUITY", "sector": "", "industry": ""}
            result = get_ticker_metadata("AAPL")
        assert result["sector"] is None
        assert result["industry"] is None

    def test_yfinance_exception_returns_safe_defaults(self):
        with patch("yfinance.Ticker") as mock_yf:
            type(mock_yf.return_value).info = property(lambda self: (_ for _ in ()).throw(Exception("network")))
            result = get_ticker_metadata("AAPL")
        assert result["subcategory"] is None
        assert result["sector"] is None
        assert result["industry"] is None

    def test_returns_all_three_keys(self):
        with patch("yfinance.Ticker") as mock_yf:
            mock_yf.return_value.info = {"quoteType": "EQUITY", "sector": "Technology", "industry": "Software"}
            result = get_ticker_metadata("MSFT")
        assert set(result.keys()) >= {"subcategory", "sector", "industry"}


class TestGetTickerSubcategoryShim:
    def test_returns_subcategory_string(self):
        with patch("bot.services.market.get_ticker_metadata", return_value={"subcategory": "stocks", "sector": "Tech", "industry": "Software"}):
            assert get_ticker_subcategory("AAPL") == "stocks"

    def test_returns_none_when_unknown(self):
        with patch("bot.services.market.get_ticker_metadata", return_value={"subcategory": None, "sector": None, "industry": None}):
            assert get_ticker_subcategory("FAKE") is None


class TestClearPriceCacheFor:
    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        market._price_cache.clear()
        yield
        market._price_cache.clear()

    def test_removes_only_given_tickers(self):
        market._price_cache["AAPL"] = ({"ticker": "AAPL"}, 0.0)
        market._price_cache["MSFT"] = ({"ticker": "MSFT"}, 0.0)
        removed = clear_price_cache_for(["AAPL"])
        assert removed == 1
        assert "AAPL" not in market._price_cache
        assert "MSFT" in market._price_cache

    def test_missing_ticker_is_noop(self):
        removed = clear_price_cache_for(["NOTCACHED"])
        assert removed == 0


class TestGetTickerDataDayChange:
    @pytest.fixture(autouse=True)
    def _clean_cache(self):
        market._price_cache.clear()
        yield
        market._price_cache.clear()

    def _mock_history(self, df: pd.DataFrame):
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = df
        return patch("yfinance.Ticker", return_value=mock_ticker)

    def test_day_change_zero_when_market_closed_today(self):
        """Last bar is Friday, 'today' (in the mock) is two days later — market hasn't traded since."""
        now = pd.Timestamp.now(tz=_TZ)
        df = _history_df([100, 101, 102, 103, 104], end=now.normalize() - pd.Timedelta(days=2))
        with self._mock_history(df):
            data = get_ticker_data("CLOSEDTEST")
        assert data["day_change_pct"] == 0.0

    def test_day_change_computed_when_market_open_today(self):
        now = pd.Timestamp.now(tz=_TZ)
        df = _history_df([100, 101, 102, 103, 104], end=now.normalize())
        with self._mock_history(df):
            data = get_ticker_data("OPENTEST")
        expected = (104 - 103) / 103 * 100
        assert data["day_change_pct"] == pytest.approx(expected)

    def test_week_change_fallback_unaffected_by_closed_market(self):
        """day_change_pct is zeroed on a closed-market day, but week_change_pct's
        fallback (used when there's under 6 sessions of history) must still reflect
        the real last session-over-session move, not the zeroed display value."""
        now = pd.Timestamp.now(tz=_TZ)
        df = _history_df([100, 101, 102], end=now.normalize() - pd.Timedelta(days=2))
        with self._mock_history(df):
            data = get_ticker_data("THINWEEKENDTEST")
        assert data["day_change_pct"] == 0.0
        expected = (102 - 101) / 101 * 100
        assert data["week_change_pct"] == pytest.approx(expected)

    def test_zero_and_nan_close_rows_are_filtered(self):
        now = pd.Timestamp.now(tz=_TZ)
        idx = pd.date_range(end=now.normalize(), periods=4, freq="D", tz=_TZ)
        df = pd.DataFrame(
            {"Close": [10.0, 0.0, np.nan, 20.0], "High": [11, 1, 1, 21], "Low": [9, 0, 0, 19]},
            index=idx,
        )
        with self._mock_history(df):
            data = get_ticker_data("ZEROTEST")
        assert data["current_price"] == 20.0
        assert data["day_change_pct"] == pytest.approx((20 - 10) / 10 * 100)

    def test_all_invalid_close_rows_returns_none(self):
        now = pd.Timestamp.now(tz=_TZ)
        idx = pd.date_range(end=now.normalize(), periods=3, freq="D", tz=_TZ)
        df = pd.DataFrame(
            {"Close": [0.0, np.nan, 0.0], "High": [1, 1, 1], "Low": [0, 0, 0]},
            index=idx,
        )
        with self._mock_history(df):
            data = get_ticker_data("ALLINVALID")
        assert data is None


class TestFetchBrProventosLogging:
    def test_fetch_failure_logs_at_warning(self, caplog):
        with patch("bot.services.market.fetch_with_retry", side_effect=Exception("boom")):
            with caplog.at_level(logging.WARNING, logger="bot.services.market"):
                result = fetch_br_proventos("PETR4.SA")
        assert result == []
        assert any(record.levelno == logging.WARNING for record in caplog.records)
