import pytest
from bot.services.market import normalize_ticker, ts_to_date


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
