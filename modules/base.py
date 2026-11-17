import time
import requests


class BaseScraper:
    name = "base"
    supports = []
    delay = 1.5  # seconds to wait before every request

    def __init__(self, timeout=10, retries=2):
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Specter/1.0"
        })

    def can_run(self, target_type):
        return target_type in self.supports

    def safe_get(self, url, **kwargs):
        """Returns (response, error). One of them is always None."""
        err = "unknown error"
        for _ in range(self.retries + 1):
            time.sleep(self.delay)  # rate limiting
            try:
                r = self.session.get(url, timeout=self.timeout, **kwargs)
                if r.status_code == 429:  # site says "slow down"
                    err = "rate limited"
                    try:
                        wait = int(r.headers.get("Retry-After", 5))
                    except ValueError:
                        wait = 5
                    time.sleep(max(0, min(wait, 30)))
                    continue
                return r, None
            except requests.exceptions.Timeout:
                err = "timeout"
            except requests.exceptions.ConnectionError:
                err = "site unreachable"
            except requests.exceptions.RequestException as e:
                err = type(e).__name__
        return None, err

    def run(self, target):
        raise NotImplementedError