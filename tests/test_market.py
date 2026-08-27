import pytest
from unittest.mock import patch
import bot.services.market as market
from bot.services.market import (
    normalize_ticker, ts_to_date, get_ticker_metadata, get_ticker_subcategory,
    clear_price_cache_for,
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
