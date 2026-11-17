from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from colorama import Fore

from .base import BaseScraper


DORKS = [
    ('"{t}"',                   "General mentions"),
    ('"{t}" site:linkedin.com', "LinkedIn"),
    ('"{t}" site:github.com',   "GitHub mentions"),
]


class DorkModule(BaseScraper):
    name = "dork"
    supports = ["email", "username", "phone"]
    delay = 8.0  # slow and polite, search engines are strict

    URL = "https://html.duckduckgo.com/html/"

    def _clean(self, href):
        """DDG wraps links in a redirect, so pull out the real URL."""
        if "uddg=" in href:
            real = parse_qs(urlparse(href).query).get("uddg")
            if real:
                return real[0]
        return href

    @staticmethod
    def _row(source, state, url="", detail=""):
        return {
            "source": source,
            "url": url,
            "state": state,
            "found": state == "FOUND",
            "detail": detail,
        }

    def run(self, target):
        results = []
        for template, label in DORKS:
            query = template.format(t=target)
            r, err = self.safe_get(self.URL, params={"q": query})

            if err:
                results.append(self._row(
                    f"Dork: {label}", "COULD NOT CHECK", detail=f"error: {err}"
                ))
                continue

            if r.status_code != 200:
                print(Fore.YELLOW + f"      [!] DuckDuckGo search unavailable "
                      f"(HTTP {r.status_code}). Stopping dorks.")
                results.append(self._row(
                    f"Dork: {label}",
                    "COULD NOT CHECK",
                    detail=f"search unavailable (HTTP {r.status_code})",
                ))
                break

            soup = BeautifulSoup(r.text, "html.parser")
            links = soup.select("a.result__a")[:3]  # top 3 hits per dork

            if not links:
                results.append(self._row(
                    f"Dork: {label}",
                    "COULD NOT CHECK",
                    detail="No result links parsed; the page may be empty or its format may have changed",
                ))
            for a in links:
                results.append(self._row(
                    f"Dork: {label}",
                    "FOUND",
                    url=self._clean(a.get("href", "")),
                    detail=a.get_text(strip=True)[:80],
                ))
        return results