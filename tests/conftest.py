import pytest
from unittest.mock import patch
from bot.db.database import init_db


@pytest.fixture
def db(tmp_path):
    """Temporary SQLite DB with full schema. Patches DATABASE_PATH for each test."""
    path = str(tmp_path / "test.db")
    with patch("bot.db.database.DATABASE_PATH", path):
        init_db()
        yield path
