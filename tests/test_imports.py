import importlib
import pytest

MODULES = [
    "bot.commands.alerts",
    "bot.commands.cache_cmd",
    "bot.commands.ceiling_cmd",
    "bot.commands.dividends_cmd",
    "bot.commands.help_cmd",
    "bot.commands.note_cmd",
    "bot.commands.resetdb_cmd",
    "bot.commands.schedule_cmd",
    "bot.commands.summary",
    "bot.commands.ticker",
    "bot.application.summary_use_case",
    "bot.application.dividends_use_case",
    "bot.application.market_cache",
    "bot.services.market",
    "bot.services.fear_greed",
    "bot.services.sentiment",
    "bot.shared.formatting",
    "bot.shared.context",
    "bot.shared.retry",
    "bot.shared.embeds",
    "bot.shared.summary_embed",
    "bot.shared.dividends_embed",
    "bot.shared.help_embed",
    "bot.shared.cache_embed",
    "bot.db.repository",
    "bot.scheduler",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_without_error(module):
    importlib.import_module(module)
