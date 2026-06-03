import pytest
from unittest.mock import MagicMock, patch

from bot.db.database import init_db
from bot.db import repository as repo
from bot.utils import ticker_autocomplete


def _interaction(discord_id: str) -> MagicMock:
    m = MagicMock()
    m.user.id = discord_id
    return m


@pytest.fixture(autouse=True)
def db(tmp_path):
    path = str(tmp_path / "test.db")
    with patch("bot.db.database.DATABASE_PATH", path):
        init_db()
        yield


class TestTickerAutocomplete:
    @pytest.mark.asyncio
    async def test_returns_all_when_current_is_empty(self):
        user = repo.get_or_create_user("1")
        repo.add_ticker(user["id"], "AAPL", "wallet")
        repo.add_ticker(user["id"], "MSFT", "watchlist")
        choices = await ticker_autocomplete(_interaction("1"), "")
        names = [c.name for c in choices]
        assert "AAPL" in names
        assert "MSFT" in names
        assert len(choices) == 2

    @pytest.mark.asyncio
    async def test_filters_by_partial_match(self):
        user = repo.get_or_create_user("2")
        repo.add_ticker(user["id"], "AAPL", "wallet")
        repo.add_ticker(user["id"], "AMZN", "wallet")
        repo.add_ticker(user["id"], "MSFT", "watchlist")
        choices = await ticker_autocomplete(_interaction("2"), "A")
        names = [c.name for c in choices]
        assert "AAPL" in names
        assert "AMZN" in names
        assert "MSFT" not in names

    @pytest.mark.asyncio
    async def test_filter_is_case_insensitive(self):
        user = repo.get_or_create_user("3")
        repo.add_ticker(user["id"], "PETR4.SA", "wallet")
        choices = await ticker_autocomplete(_interaction("3"), "petr")
        assert len(choices) == 1
        assert choices[0].name == "PETR4.SA"

    @pytest.mark.asyncio
    async def test_no_tickers_returns_empty(self):
        choices = await ticker_autocomplete(_interaction("99"), "")
        assert choices == []

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self):
        user = repo.get_or_create_user("4")
        repo.add_ticker(user["id"], "AAPL", "wallet")
        choices = await ticker_autocomplete(_interaction("4"), "XYZ")
        assert choices == []

    @pytest.mark.asyncio
    async def test_respects_25_choice_limit(self):
        user = repo.get_or_create_user("5")
        for i in range(30):
            repo.add_ticker(user["id"], f"T{i:02d}.SA", "watchlist")
        choices = await ticker_autocomplete(_interaction("5"), "")
        assert len(choices) <= 25

    @pytest.mark.asyncio
    async def test_choice_name_and_value_match(self):
        user = repo.get_or_create_user("6")
        repo.add_ticker(user["id"], "BTC-USD", "wallet")
        choices = await ticker_autocomplete(_interaction("6"), "BTC")
        assert len(choices) == 1
        assert choices[0].name == choices[0].value == "BTC-USD"

    @pytest.mark.asyncio
    async def test_returns_empty_on_db_error(self):
        with patch("bot.db.repository.get_or_create_user", side_effect=Exception("DB down")):
            choices = await ticker_autocomplete(_interaction("7"), "")
        assert choices == []
