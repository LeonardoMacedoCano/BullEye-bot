import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bot.scheduler import _check_fgi_alerts


def _alert(alert_id, discord_id, target_value):
    return {"id": alert_id, "discord_id": str(discord_id), "target_value": target_value}


def _run(coro):
    return asyncio.run(coro)


class TestCheckFgiAlerts:
    def test_skips_when_no_active_alerts(self):
        bot = MagicMock()
        bot.fetch_user = AsyncMock()
        with patch("bot.scheduler.get_active_fgi_alerts", return_value=[]):
            _run(_check_fgi_alerts(bot))
        bot.fetch_user.assert_not_called()

    def test_skips_when_fgi_fetch_fails(self):
        bot = MagicMock()
        bot.fetch_user = AsyncMock()
        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=[_alert(1, "111", 30)]),
            patch("bot.scheduler.get_fear_greed_index", return_value=None),
        ):
            _run(_check_fgi_alerts(bot))
        bot.fetch_user.assert_not_called()

    def test_triggers_when_fgi_below_target(self):
        mock_user = MagicMock()
        mock_user.mention = "<@222>"
        mock_user.send = AsyncMock()
        bot = MagicMock()
        bot.fetch_user = AsyncMock(return_value=mock_user)

        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=[_alert(1, "222", 30)]),
            patch("bot.scheduler.get_fear_greed_index", return_value={"value": 28, "classification": "Extreme Fear"}),
            patch("bot.scheduler.deactivate_fgi_alert") as mock_deactivate,
        ):
            _run(_check_fgi_alerts(bot))

        mock_deactivate.assert_called_once_with(1)
        mock_user.send.assert_called_once()
        msg = mock_user.send.call_args[0][0]
        assert "28" in msg
        assert "30" in msg

    def test_triggers_when_fgi_exactly_at_target(self):
        mock_user = MagicMock()
        mock_user.mention = "<@333>"
        mock_user.send = AsyncMock()
        bot = MagicMock()
        bot.fetch_user = AsyncMock(return_value=mock_user)

        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=[_alert(2, "333", 50)]),
            patch("bot.scheduler.get_fear_greed_index", return_value={"value": 50, "classification": "Neutral"}),
            patch("bot.scheduler.deactivate_fgi_alert") as mock_deactivate,
        ):
            _run(_check_fgi_alerts(bot))

        mock_deactivate.assert_called_once_with(2)
        mock_user.send.assert_called_once()

    def test_does_not_trigger_when_fgi_above_target(self):
        bot = MagicMock()
        bot.fetch_user = AsyncMock()
        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=[_alert(3, "444", 30)]),
            patch("bot.scheduler.get_fear_greed_index", return_value={"value": 55, "classification": "Greed"}),
            patch("bot.scheduler.deactivate_fgi_alert") as mock_deactivate,
        ):
            _run(_check_fgi_alerts(bot))

        mock_deactivate.assert_not_called()
        bot.fetch_user.assert_not_called()

    def test_only_matching_alerts_trigger(self):
        # FGI=25: alert target=25 triggers (25<=25), alert target=15 does not (25>15)
        mock_user = MagicMock()
        mock_user.mention = "<@555>"
        mock_user.send = AsyncMock()
        bot = MagicMock()
        bot.fetch_user = AsyncMock(return_value=mock_user)

        alerts = [_alert(4, "555", 25), _alert(5, "666", 15)]
        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=alerts),
            patch("bot.scheduler.get_fear_greed_index", return_value={"value": 25, "classification": "Extreme Fear"}),
            patch("bot.scheduler.deactivate_fgi_alert") as mock_deactivate,
        ):
            _run(_check_fgi_alerts(bot))

        mock_deactivate.assert_called_once_with(4)
        mock_user.send.assert_called_once()

    def test_dm_failure_does_not_raise(self):
        mock_user = MagicMock()
        mock_user.mention = "<@777>"
        mock_user.send = AsyncMock(side_effect=Exception("DM blocked"))
        bot = MagicMock()
        bot.fetch_user = AsyncMock(return_value=mock_user)

        with (
            patch("bot.scheduler.get_active_fgi_alerts", return_value=[_alert(6, "777", 40)]),
            patch("bot.scheduler.get_fear_greed_index", return_value={"value": 35, "classification": "Fear"}),
            patch("bot.scheduler.deactivate_fgi_alert"),
        ):
            _run(_check_fgi_alerts(bot))
