import logging
import requests

logger = logging.getLogger(__name__)

_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


def get_fear_greed_index() -> dict | None:
    try:
        response = requests.get(_FEAR_GREED_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        entry = data["data"][0]
        return {
            "value": int(entry["value"]),
            "classification": entry["value_classification"],
        }
    except Exception as exc:
        logger.warning("Failed to fetch Fear & Greed index: %s", exc)
        return None
