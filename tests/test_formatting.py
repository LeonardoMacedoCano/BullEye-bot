import pytest
from bot.shared.formatting import (
    MSG_LIMIT, display_name, currency, fmt, fmt_pct,
    render_table, pack_messages, group_by_subcategory,
)


def test_msg_limit_value():
    assert MSG_LIMIT == 1900


class TestDisplayName:
    def test_btc_usd(self):
        assert display_name("BTC-USD") == "BTC"

    def test_btc_usd_lowercase(self):
        assert display_name("btc-usd") == "BTC"

    def test_br_stock_strips_sa(self):
        assert display_name("PETR4.SA") == "PETR4"

    def test_us_stock_unchanged(self):
        assert display_name("AAPL") == "AAPL"

    def test_etf_unchanged(self):
        assert display_name("SPY") == "SPY"


class TestCurrency:
    def test_br_stock_returns_brl(self):
        assert currency("PETR4.SA") == "R$"

    def test_us_stock_returns_usd(self):
        assert currency("AAPL") == "$"

    def test_crypto_returns_usd(self):
        assert currency("BTC-USD") == "$"


class TestFmt:
    def test_usd_format(self):
        assert fmt(1234.56, "$") == "$1,234.56"

    def test_brl_format(self):
        assert fmt(50.00, "R$") == "R$50.00"

    def test_large_value(self):
        assert fmt(1_000_000.0, "$") == "$1,000,000.00"


class TestFmtPct:
    def test_positive_has_plus_sign(self):
        assert fmt_pct(1.5) == "+1.5%"

    def test_negative_has_minus_sign(self):
        assert fmt_pct(-2.3) == "-2.3%"

    def test_zero_has_plus_sign(self):
        assert fmt_pct(0.0) == "+0.0%"

    def test_rounds_to_one_decimal(self):
        assert fmt_pct(1.567) == "+1.6%"


class TestRenderTable:
    def test_basic_table_contains_headers_and_data(self):
        result = render_table(["Name", "Value"], [["foo", "42"]])
        assert "Name" in result
        assert "Value" in result
        assert "foo" in result
        assert "42" in result
        assert "─" in result

    def test_empty_rows_returns_empty_string(self):
        assert render_table(["A", "B"], []) == ""

    def test_all_dash_column_excluded_by_default(self):
        result = render_table(["Name", "Optional"], [["foo", "—"], ["bar", "—"]])
        assert "Optional" not in result

    def test_required_header_shown_even_if_all_dashes(self):
        result = render_table(
            ["Name", "Optional"],
            [["foo", "—"]],
            required_headers=["Optional"],
        )
        assert "Optional" in result

    def test_separator_length_matches_content(self):
        result = render_table(["A", "B"], [["x", "y"]])
        lines = result.splitlines()
        assert len(lines) == 3  # header, separator, data row


class TestPackMessages:
    def test_single_section_returned_as_is(self):
        assert pack_messages(["hello"]) == ["hello"]

    def test_two_small_sections_merged(self):
        result = pack_messages(["a", "b"])
        assert result == ["a\nb"]

    def test_overflow_causes_split(self):
        big = "x" * 1000
        result = pack_messages([big, big])
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        assert pack_messages([]) == []

    def test_total_length_respects_msg_limit(self):
        sections = ["a" * 950, "b" * 950]
        result = pack_messages(sections)
        for msg in result:
            assert len(msg) <= MSG_LIMIT


class TestGroupBySubcategory:
    ORDER = ["br-stocks", "crypto", "etf", "stocks"]

    def test_ordering_respected(self):
        rows = [
            {"subcategory": "stocks"},
            {"subcategory": "br-stocks"},
            {"subcategory": "crypto"},
        ]
        result = group_by_subcategory(rows, self.ORDER)
        keys = [k for k, _ in result]
        assert keys == ["br-stocks", "crypto", "stocks"]

    def test_none_subcategory_goes_last(self):
        rows = [{"subcategory": None}, {"subcategory": "br-stocks"}]
        result = group_by_subcategory(rows, self.ORDER)
        assert result[-1][0] is None

    def test_missing_subcategory_key_treated_as_none(self):
        rows = [{"ticker": "AAPL"}]  # no "subcategory" key
        result = group_by_subcategory(rows, self.ORDER)
        assert result[0][0] is None

    def test_unknown_subcategory_appended_after_known(self):
        rows = [{"subcategory": "reit"}, {"subcategory": "br-stocks"}]
        result = group_by_subcategory(rows, self.ORDER)
        keys = [k for k, _ in result]
        assert keys[0] == "br-stocks"
        assert "reit" in keys

    def test_group_counts_match(self):
        rows = [
            {"subcategory": "stocks"},
            {"subcategory": "stocks"},
            {"subcategory": "crypto"},
        ]
        result = group_by_subcategory(rows, self.ORDER)
        groups = dict(result)
        assert len(groups["stocks"]) == 2
        assert len(groups["crypto"]) == 1
