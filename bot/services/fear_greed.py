import logging
import time
import requests

logger = logging.getLogger(__name__)

_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
_CACHE_TTL = 1800  # 30 minutes

_cached: dict | None = None
_cached_at: float = 0.0


def get_fear_greed_index() -> dict | None:
    global _cached, _cached_at
    if _cached is not None and (time.time() - _cached_at) < _CACHE_TTL:
        return _cached
    try:
        response = requests.get(_FEAR_GREED_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        entry = data["data"][0]
        _cached = {
            "value": int(entry["value"]),
            "classification": entry["value_classification"],
        }
        _cached_at = time.time()
        return _cached
    except Exception as exc:
        logger.warning("Failed to fetch Fear & Greed index: %s", exc)
        return _cached
