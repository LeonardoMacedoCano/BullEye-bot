import logging
import threading
import time
import requests

logger = logging.getLogger(__name__)

_FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"
_CACHE_TTL = 1800

_cached: dict | None = None
_cached_at: float = 0.0
_cache_lock = threading.Lock()


def clear_fear_greed_cache() -> None:
    global _cached, _cached_at
    with _cache_lock:
        _cached = None
        _cached_at = 0.0


def get_fear_greed_index() -> dict | None:
    global _cached, _cached_at
    with _cache_lock:
        if _cached is not None and (time.time() - _cached_at) < _CACHE_TTL:
            return _cached
    try:
        response = requests.get(_FEAR_GREED_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        entry = data["data"][0]
        result = {
            "value": int(entry["value"]),
            "classification": entry["value_classification"],
        }
        with _cache_lock:
            _cached = result
            _cached_at = time.time()
        return result
    except Exception as exc:
        logger.warning("Failed to fetch Fear & Greed index: %s", exc)
        with _cache_lock:
            return _cached
