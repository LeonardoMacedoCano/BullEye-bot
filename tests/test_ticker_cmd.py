from bot.commands.ticker import _fmt_sector


def _row(sector, industry):
    return {"sector": sector, "industry": industry}


class TestFmtSector:
    def test_both_present_combined_with_slash(self):
        assert _fmt_sector(_row("Technology", "Consumer Electronics")) == "Technology / Consumer Electronics"

    def test_only_sector_present(self):
        assert _fmt_sector(_row("Energy", None)) == "Energy"

    def test_only_industry_present(self):
        assert _fmt_sector(_row(None, "Banks")) == "Banks"

    def test_both_none_returns_dash(self):
        assert _fmt_sector(_row(None, None)) == "—"

    def test_empty_strings_return_dash(self):
        assert _fmt_sector(_row("", "")) == "—"

    def test_sector_empty_industry_present(self):
        assert _fmt_sector(_row("", "Insurance")) == "Insurance"

    def test_industry_empty_sector_present(self):
        assert _fmt_sector(_row("Financial Services", "")) == "Financial Services"

    def test_long_value_returned_verbatim(self):
        long = "Financial Services / Insurance - Property & Casualty"
        assert _fmt_sector(_row("Financial Services", "Insurance - Property & Casualty")) == long
