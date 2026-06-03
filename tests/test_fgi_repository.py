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


class TestFgiCeiling:
    def test_get_not_set_returns_none(self):
        user = repo.get_or_create_user("100")
        assert repo.get_user_fgi_ceiling(user["id"]) is None

    def test_set_and_get(self):
        user = repo.get_or_create_user("101")
        repo.set_user_fgi_ceiling(user["id"], 75)
        assert repo.get_user_fgi_ceiling(user["id"]) == 75

    def test_update_replaces_existing(self):
        user = repo.get_or_create_user("102")
        repo.set_user_fgi_ceiling(user["id"], 75)
        repo.set_user_fgi_ceiling(user["id"], 50)
        assert repo.get_user_fgi_ceiling(user["id"]) == 50

    def test_clear_removes_ceiling(self):
        user = repo.get_or_create_user("103")
        repo.set_user_fgi_ceiling(user["id"], 60)
        repo.clear_user_fgi_ceiling(user["id"])
        assert repo.get_user_fgi_ceiling(user["id"]) is None

    def test_clear_on_unset_is_noop(self):
        user = repo.get_or_create_user("104")
        repo.clear_user_fgi_ceiling(user["id"])
        assert repo.get_user_fgi_ceiling(user["id"]) is None

    def test_isolated_per_user(self):
        u1 = repo.get_or_create_user("105")
        u2 = repo.get_or_create_user("106")
        repo.set_user_fgi_ceiling(u1["id"], 80)
        assert repo.get_user_fgi_ceiling(u2["id"]) is None

    def test_boundary_min(self):
        user = repo.get_or_create_user("107")
        repo.set_user_fgi_ceiling(user["id"], 1)
        assert repo.get_user_fgi_ceiling(user["id"]) == 1

    def test_boundary_max(self):
        user = repo.get_or_create_user("108")
        repo.set_user_fgi_ceiling(user["id"], 100)
        assert repo.get_user_fgi_ceiling(user["id"]) == 100


class TestFgiAlerts:
    def test_empty_when_no_alerts(self):
        assert repo.get_active_fgi_alerts() == []

    def test_add_and_get_active(self):
        user = repo.get_or_create_user("110")
        repo.add_fgi_alert(user["id"], 30)
        alerts = repo.get_active_fgi_alerts()
        assert len(alerts) == 1
        assert alerts[0]["target_value"] == 30

    def test_discord_id_included_in_result(self):
        user = repo.get_or_create_user("111")
        repo.add_fgi_alert(user["id"], 35)
        alerts = repo.get_active_fgi_alerts()
        assert alerts[0]["discord_id"] == "111"

    def test_deactivate_removes_from_active(self):
        user = repo.get_or_create_user("112")
        repo.add_fgi_alert(user["id"], 25)
        alerts = repo.get_active_fgi_alerts()
        repo.deactivate_fgi_alert(alerts[0]["id"])
        assert repo.get_active_fgi_alerts() == []

    def test_multiple_users_all_returned(self):
        u1 = repo.get_or_create_user("113")
        u2 = repo.get_or_create_user("114")
        repo.add_fgi_alert(u1["id"], 20)
        repo.add_fgi_alert(u2["id"], 40)
        assert len(repo.get_active_fgi_alerts()) == 2

    def test_inactive_not_returned_active_still_is(self):
        user = repo.get_or_create_user("115")
        repo.add_fgi_alert(user["id"], 50)
        alerts = repo.get_active_fgi_alerts()
        repo.deactivate_fgi_alert(alerts[0]["id"])
        repo.add_fgi_alert(user["id"], 60)
        active = repo.get_active_fgi_alerts()
        assert len(active) == 1
        assert active[0]["target_value"] == 60

    def test_multiple_alerts_same_user(self):
        user = repo.get_or_create_user("116")
        repo.add_fgi_alert(user["id"], 20)
        repo.add_fgi_alert(user["id"], 30)
        assert len(repo.get_active_fgi_alerts()) == 2
