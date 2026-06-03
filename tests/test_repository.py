import pytest
from unittest.mock import patch
from bot.db.database import init_db
from bot.db import repository as repo


@pytest.fixture(autouse=True)
def db(tmp_path):
    path = str(tmp_path / "test.db")
    with patch("bot.db.database.DATABASE_PATH", path):
        init_db()
        yield


class TestUsers:
    def test_create_user_returns_row(self):
        user = repo.get_or_create_user("123")
        assert user["discord_id"] == "123"
        assert user["id"] is not None

    def test_idempotent_same_id(self):
        u1 = repo.get_or_create_user("999")
        u2 = repo.get_or_create_user("999")
        assert u1["id"] == u2["id"]

    def test_different_users_different_ids(self):
        u1 = repo.get_or_create_user("aaa")
        u2 = repo.get_or_create_user("bbb")
        assert u1["id"] != u2["id"]


class TestTickers:
    def test_add_and_list(self):
        user = repo.get_or_create_user("1")
        repo.add_ticker(user["id"], "AAPL", "wallet")
        rows = repo.list_tickers(user["id"])
        assert len(rows) == 1
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["category"] == "wallet"

    def test_add_multiple_tickers(self):
        user = repo.get_or_create_user("2")
        repo.add_ticker(user["id"], "AAPL", "wallet")
        repo.add_ticker(user["id"], "MSFT", "watchlist")
        rows = repo.list_tickers(user["id"])
        assert len(rows) == 2

    def test_remove_existing_ticker(self):
        user = repo.get_or_create_user("3")
        repo.add_ticker(user["id"], "TSLA", "watchlist")
        count = repo.remove_ticker(user["id"], "TSLA")
        assert count == 1
        assert repo.list_tickers(user["id"]) == []

    def test_remove_nonexistent_returns_zero(self):
        user = repo.get_or_create_user("4")
        assert repo.remove_ticker(user["id"], "FAKE") == 0

    def test_ticker_exists_true(self):
        user = repo.get_or_create_user("5")
        repo.add_ticker(user["id"], "NVDA", "wallet")
        assert repo.ticker_exists(user["id"], "NVDA") is True

    def test_ticker_exists_false(self):
        user = repo.get_or_create_user("6")
        assert repo.ticker_exists(user["id"], "NOPE") is False

    def test_get_ticker_category(self):
        user = repo.get_or_create_user("7")
        repo.add_ticker(user["id"], "SPY", "watchlist")
        assert repo.get_ticker_category(user["id"], "SPY") == "watchlist"

    def test_get_ticker_category_missing_returns_none(self):
        user = repo.get_or_create_user("8")
        assert repo.get_ticker_category(user["id"], "MISSING") is None

    def test_remove_also_deactivates_alerts(self):
        user = repo.get_or_create_user("9")
        repo.add_ticker(user["id"], "BTC-USD", "wallet")
        repo.add_alert(user["id"], "BTC-USD", 50000.0)
        repo.remove_ticker(user["id"], "BTC-USD")
        assert repo.get_active_alerts(user["id"]) == []


class TestCeiling:
    def test_set_and_read(self):
        user = repo.get_or_create_user("10")
        repo.add_ticker(user["id"], "PETR4.SA", "wallet")
        repo.set_user_ceiling(user["id"], "PETR4.SA", 35.50)
        row = repo.get_ticker_row(user["id"], "PETR4.SA")
        assert row["user_ceiling"] == pytest.approx(35.50)

    def test_clear_sets_to_none(self):
        user = repo.get_or_create_user("11")
        repo.add_ticker(user["id"], "VALE3.SA", "wallet")
        repo.set_user_ceiling(user["id"], "VALE3.SA", 70.0)
        repo.clear_user_ceiling(user["id"], "VALE3.SA")
        row = repo.get_ticker_row(user["id"], "VALE3.SA")
        assert row["user_ceiling"] is None

    def test_ceiling_not_set_by_default(self):
        user = repo.get_or_create_user("12")
        repo.add_ticker(user["id"], "AAPL", "watchlist")
        row = repo.get_ticker_row(user["id"], "AAPL")
        assert row["user_ceiling"] is None


class TestNotes:
    def test_set_and_read(self):
        user = repo.get_or_create_user("13")
        repo.add_ticker(user["id"], "AAPL", "watchlist")
        repo.set_user_note(user["id"], "AAPL", "Buy below 150")
        row = repo.get_ticker_row(user["id"], "AAPL")
        assert row["note"] == "Buy below 150"

    def test_clear_sets_to_none(self):
        user = repo.get_or_create_user("14")
        repo.add_ticker(user["id"], "MSFT", "watchlist")
        repo.set_user_note(user["id"], "MSFT", "some note")
        repo.clear_user_note(user["id"], "MSFT")
        row = repo.get_ticker_row(user["id"], "MSFT")
        assert row["note"] is None


class TestAlerts:
    def test_add_and_get(self):
        user = repo.get_or_create_user("15")
        repo.add_ticker(user["id"], "BTC-USD", "wallet")
        repo.add_alert(user["id"], "BTC-USD", 50000.0)
        alerts = repo.get_active_alerts(user["id"])
        assert len(alerts) == 1
        assert alerts[0]["target_price"] == pytest.approx(50000.0)

    def test_deactivate_removes_from_active(self):
        user = repo.get_or_create_user("16")
        repo.add_ticker(user["id"], "ETH-USD", "watchlist")
        repo.add_alert(user["id"], "ETH-USD", 3000.0)
        alerts = repo.get_active_alerts(user["id"])
        repo.deactivate_alert(alerts[0]["id"])
        assert repo.get_active_alerts(user["id"]) == []

    def test_get_all_active_alerts_no_filter(self):
        u1 = repo.get_or_create_user("17")
        u2 = repo.get_or_create_user("18")
        repo.add_ticker(u1["id"], "AAPL", "wallet")
        repo.add_ticker(u2["id"], "MSFT", "wallet")
        repo.add_alert(u1["id"], "AAPL", 100.0)
        repo.add_alert(u2["id"], "MSFT", 200.0)
        all_alerts = repo.get_active_alerts()
        assert len(all_alerts) == 2


class TestSchedules:
    def test_set_and_get(self):
        user = repo.get_or_create_user("19")
        repo.set_schedule(user["id"], "08:00")
        sched = repo.get_schedule(user["id"])
        assert sched["time"] == "08:00"

    def test_deactivate_makes_get_return_none(self):
        user = repo.get_or_create_user("20")
        repo.set_schedule(user["id"], "09:00")
        repo.deactivate_schedule(user["id"])
        assert repo.get_schedule(user["id"]) is None

    def test_upsert_updates_existing_time(self):
        user = repo.get_or_create_user("21")
        repo.set_schedule(user["id"], "07:00")
        repo.set_schedule(user["id"], "10:00")
        sched = repo.get_schedule(user["id"])
        assert sched["time"] == "10:00"

    def test_get_all_active_schedules(self):
        u1 = repo.get_or_create_user("22")
        u2 = repo.get_or_create_user("23")
        repo.set_schedule(u1["id"], "08:00")
        repo.set_schedule(u2["id"], "09:00")
        schedules = repo.get_all_active_schedules()
        assert len(schedules) == 2

    def test_update_last_sent_date(self):
        user = repo.get_or_create_user("24")
        repo.set_schedule(user["id"], "08:00")
        repo.update_last_sent_date(user["id"], "2025-01-01")
        sched = repo.get_schedule(user["id"])
        assert sched["last_sent_date"] == "2025-01-01"


class TestPriceCache:
    def test_set_and_get(self):
        repo.set_price_cache("AAPL", 2.5, 0.015)
        row = repo.get_price_cache("AAPL")
        assert row is not None
        assert row["dy_rate"] == pytest.approx(2.5)
        assert row["dy_yield"] == pytest.approx(0.015)

    def test_get_missing_returns_none(self):
        assert repo.get_price_cache("NOTEXIST") is None

    def test_clear_removes_all(self):
        repo.set_price_cache("AAPL", 1.0, 0.01)
        repo.set_price_cache("MSFT", 2.0, 0.02)
        deleted = repo.clear_price_cache_db()
        assert deleted == 2
        assert repo.get_price_cache("AAPL") is None


class TestProventos:
    def test_upsert_and_get(self):
        ticker_id = repo.upsert_ticker("PETR4.SA", "br-stocks", None)
        repo.upsert_provento(ticker_id, "2024-01-15", "2024-02-01", 1.50, "Dividendo", None)
        rows = repo.get_proventos_for_ticker(ticker_id)
        assert len(rows) == 1
        assert rows[0]["ex_date"] == "2024-01-15"
        assert rows[0]["amount"] == pytest.approx(1.50)

    def test_upsert_is_idempotent_on_conflict(self):
        ticker_id = repo.upsert_ticker("VALE3.SA", "br-stocks", None)
        repo.upsert_provento(ticker_id, "2024-03-01", None, 2.0, "Dividendo", None)
        repo.upsert_provento(ticker_id, "2024-03-01", "2024-04-01", 2.5, "Dividendo", "Updated")
        rows = repo.get_proventos_for_ticker(ticker_id)
        assert len(rows) == 1
        assert rows[0]["amount"] == pytest.approx(2.5)
        assert rows[0]["pay_date"] == "2024-04-01"

    def test_upcoming_proventos_in_window(self):
        from datetime import date, timedelta
        ticker_id = repo.upsert_ticker("ITUB4.SA", "br-stocks", None)
        future = (date.today() + timedelta(days=10)).isoformat()
        repo.upsert_provento(ticker_id, future, None, 0.75, "Dividendo", None)
        rows = repo.get_proventos_upcoming(["ITUB4.SA"])
        assert len(rows) == 1
        assert rows[0]["symbol"] == "ITUB4.SA"

    def test_upcoming_excludes_past(self):
        ticker_id = repo.upsert_ticker("BBDC4.SA", "br-stocks", None)
        repo.upsert_provento(ticker_id, "2020-01-01", None, 1.0, "Dividendo", None)
        rows = repo.get_proventos_upcoming(["BBDC4.SA"])
        assert rows == []

    def test_clear_proventos(self):
        ticker_id = repo.upsert_ticker("ITSA4.SA", "br-stocks", None)
        repo.upsert_provento(ticker_id, "2024-06-01", None, 0.50, "Dividendo", None)
        deleted = repo.clear_proventos_db()
        assert deleted == 1
        assert repo.get_proventos_for_ticker(ticker_id) == []


class TestTickerSectorIndustry:
    def test_add_ticker_stores_sector_and_industry(self):
        user = repo.get_or_create_user("50")
        repo.add_ticker(user["id"], "AAPL", "wallet", "stocks", "Technology", "Consumer Electronics")
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] == "Technology"
        assert rows[0]["industry"] == "Consumer Electronics"

    def test_add_ticker_without_sector_defaults_to_none(self):
        user = repo.get_or_create_user("51")
        repo.add_ticker(user["id"], "BTC-USD", "watchlist")
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] is None
        assert rows[0]["industry"] is None

    def test_list_tickers_exposes_sector_industry_keys(self):
        user = repo.get_or_create_user("52")
        repo.add_ticker(user["id"], "MSFT", "wallet", "stocks", "Technology", "Software")
        rows = repo.list_tickers(user["id"])
        assert "sector" in rows[0].keys()
        assert "industry" in rows[0].keys()

    def test_update_ticker_sector_industry(self):
        user = repo.get_or_create_user("53")
        repo.add_ticker(user["id"], "PETR4.SA", "wallet")
        repo.update_ticker_sector_industry("PETR4.SA", "Energy", "Oil & Gas Integrated")
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] == "Energy"
        assert rows[0]["industry"] == "Oil & Gas Integrated"

    def test_update_ticker_sector_industry_clears_to_none(self):
        user = repo.get_or_create_user("54")
        repo.add_ticker(user["id"], "VALE3.SA", "wallet", "br-stocks", "Basic Materials", "Mining")
        repo.update_ticker_sector_industry("VALE3.SA", None, None)
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] is None
        assert rows[0]["industry"] is None

    def test_upsert_ticker_stores_sector_and_industry(self):
        repo.upsert_ticker("WEGE3.SA", "br-stocks", "EQUITY", "Industrials", "Electrical Equipment & Parts")
        user = repo.get_or_create_user("55")
        repo.add_ticker(user["id"], "WEGE3.SA", "wallet")
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] == "Industrials"
        assert rows[0]["industry"] == "Electrical Equipment & Parts"

    def test_upsert_ticker_does_not_overwrite_existing_sector_with_none(self):
        repo.upsert_ticker("BBAS3.SA", "br-stocks", "EQUITY", "Financial Services", "Banks")
        repo.upsert_ticker("BBAS3.SA", "br-stocks", "EQUITY", None, None)
        user = repo.get_or_create_user("56")
        repo.add_ticker(user["id"], "BBAS3.SA", "wallet")
        rows = repo.list_tickers(user["id"])
        assert rows[0]["sector"] == "Financial Services"
        assert rows[0]["industry"] == "Banks"
