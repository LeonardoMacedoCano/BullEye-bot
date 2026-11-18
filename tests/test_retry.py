from unittest.mock import patch

import pytest

from bot.shared.retry import call_with_retry


class TestCallWithRetry:
    def test_returns_result_on_first_success(self):
        fn = lambda: "ok"
        assert call_with_retry(fn) == "ok"

    def test_retries_then_succeeds(self):
        calls = {"count": 0}

        def flaky():
            calls["count"] += 1
            if calls["count"] < 3:
                raise ConnectionError("boom")
            return "ok"

        with patch("bot.shared.retry.time.sleep"):
            result = call_with_retry(flaky)
        assert result == "ok"
        assert calls["count"] == 3

    def test_raises_last_exception_after_exhausting_attempts(self):
        def always_fails():
            raise ConnectionError("still broken")

        with patch("bot.shared.retry.time.sleep"):
            with pytest.raises(ConnectionError, match="still broken"):
                call_with_retry(always_fails, max_attempts=3)

    def test_passes_args_and_kwargs_through(self):
        def add(a, b, *, c):
            return a + b + c

        assert call_with_retry(add, 1, 2, c=3) == 6
