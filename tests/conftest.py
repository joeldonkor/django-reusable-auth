import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    # Throttle and lockout counters live in the cache, which outlives each test
    cache.clear()
    yield
    cache.clear()
