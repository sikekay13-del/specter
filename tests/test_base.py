from types import SimpleNamespace

import pytest

from modules import base
from modules.base import BaseScraper


def test_safe_get_clamps_negative_retry_after(monkeypatch):
    sleeps = []
    responses = iter([
        SimpleNamespace(status_code=429, headers={"Retry-After": "-5"}),
        SimpleNamespace(status_code=200, headers={}),
    ])
    scraper = BaseScraper(retries=1)
    scraper.delay = 0
    scraper.session.get = lambda *args, **kwargs: next(responses)
    monkeypatch.setattr(base.time, "sleep", sleeps.append)

    response, error = scraper.safe_get("https://example.test")

    assert response.status_code == 200
    assert error is None
    assert sleeps == [0, 0, 0]


@pytest.mark.parametrize(
    ("timeout", "retries"),
    [(0, 0), (-1, 0), (1, -1)],
)
def test_scraper_rejects_invalid_retry_configuration(timeout, retries):
    with pytest.raises(ValueError):
        BaseScraper(timeout=timeout, retries=retries)
