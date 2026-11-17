from bs4 import BeautifulSoup
from .base import BaseScraper

# name: (url pattern, text that appears on the page when the user does NOT exist)
# None = trust the status code (200 = exists, 404 = doesn't)
SITES = {
    # Code & dev
    "GitHub":        ("https://github.com/{}", None),
    "GitLab":        ("https://gitlab.com/{}", None),
    "Bitbucket":     ("https://bitbucket.org/{}/", None),
    "Codeberg":      ("https://codeberg.org/{}", None),
    "Dev.to":        ("https://dev.to/{}", None),
    "npm":           ("https://www.npmjs.com/~{}", None),
    "PyPI":          ("https://pypi.org/user/{}/", None),
    "Replit":        ("https://replit.com/@{}", None),
    "CodePen":       ("https://codepen.io/{}", None),
    "Kaggle":        ("https://www.kaggle.com/{}", None),
    "LeetCode":      ("https://leetcode.com/{}/", None),
    "HackerNews":    ("https://news.ycombinator.com/user?id={}", "No such user"),

    # Social & community
    "Reddit":        ("https://www.reddit.com/user/{}", None),
    "Medium":        ("https://medium.com/@{}", None),
    "Pinterest":     ("https://www.pinterest.com/{}/", None),
    "Flickr":        ("https://www.flickr.com/people/{}", None),
    "Tumblr":        ("https://{}.tumblr.com", None),
    "Mastodon":      ("https://mastodon.social/@{}", None),
    "Bluesky":       ("https://bsky.app/profile/{}", None),

    # Media & creative
    "SoundCloud":    ("https://soundcloud.com/{}", None),
    "Vimeo":         ("https://vimeo.com/{}", None),
    "Dribbble":      ("https://dribbble.com/{}", None),
    "Behance":       ("https://www.behance.net/{}", None),
    "Last.fm":       ("https://www.last.fm/user/{}", None),

    # Gaming & other
    "Steam":         ("https://steamcommunity.com/id/{}", "The specified profile could not be found"),
    "Chess.com":     ("https://www.chess.com/member/{}", None),
    "Lichess":       ("https://lichess.org/@/{}", None),
    "Keybase":       ("https://keybase.io/{}", None),
    "Gravatar":      ("https://gravatar.com/{}", None),
    "Linktree":      ("https://linktr.ee/{}", None),
    "About.me":      ("https://about.me/{}", None),
}


class SocialModule(BaseScraper):
    name = "social"
    supports = ["username"]
    delay = 1.0
    PARTIAL_SEARCH_PLATFORMS = {"GitHub", "Bluesky", "Codeberg", "Mastodon"}
    GITHUB_PAGE_SIZE = 100
    GITHUB_RESULT_LIMIT = 1000
    GITHUB_SEARCH_DELAY = 7.0
    BLUESKY_PAGE_SIZE = 100
    BLUESKY_RESULT_LIMIT = 1000
    BLUESKY_PAGE_LIMIT = 10
    BLUESKY_SEARCH_DELAY = 1.5
    CODEBERG_RESULT_LIMIT = 50
    MASTODON_RESULT_LIMIT = 40

    def __init__(self, sites=None, allow_partial=False, **kwargs):
        super().__init__(**kwargs)
        self.sites = sites or SITES
        self.allow_partial = allow_partial

    @staticmethod
    def _row(source, url, state, detail):
        return {
            "source": source,
            "url": url,
            "state": state,
            "found": state == "FOUND",
            "detail": detail,
        }

    def _check_exact(self, site, pattern, miss_text, target):
        url = pattern.format(target)
        r, err = self.safe_get(url)
        if err:
            return self._row(site, url, "COULD NOT CHECK", f"error: {err}")
        if r.status_code == 200:
            if miss_text and miss_text.lower() in r.text.lower():
                return self._row(site, url, "NOT FOUND", "page says the profile does not exist")
            soup = BeautifulSoup(r.text, "html.parser")
            title = soup.title.string.strip()[:80] if soup.title and soup.title.string else "public profile"
            return self._row(site, url, "FOUND", title)
        if r.status_code == 404:
            return self._row(site, url, "NOT FOUND", "HTTP 404")
        return self._row(site, url, "COULD NOT CHECK", f"HTTP {r.status_code}")

    def _check_github_partial(self, target):
        query = f"{target} in:login"
        url = "https://api.github.com/search/users"
        results = []
        total_count = None
        pages_checked = 0
        failure = None
        original_delay = self.delay
        try:
            self.delay = self.GITHUB_SEARCH_DELAY
            for page in range(1, self.GITHUB_RESULT_LIMIT // self.GITHUB_PAGE_SIZE + 1):
                r, err = self.safe_get(
                    url,
                    params={
                        "q": query,
                        "per_page": self.GITHUB_PAGE_SIZE,
                        "page": page,
                    },
                )
                if err:
                    failure = f"request error: {err}"
                    break
                if r.status_code != 200:
                    failure = f"HTTP {r.status_code}"
                    break
                try:
                    payload = r.json()
                    items = payload["items"]
                    total_count = int(payload["total_count"])
                except (ValueError, KeyError, TypeError, AttributeError):
                    failure = "invalid search response"
                    break

                if (
                    not isinstance(items, list)
                    or not all(isinstance(item, dict) for item in items)
                ):
                    failure = "invalid search response"
                    break
                if not items and total_count:
                    failure = "empty search page before all reported matches were checked"
                    break
                pages_checked += 1
                results.extend(
                    self._row(
                        "GitHub partial",
                        item.get("html_url", ""),
                        "FOUND",
                        item.get("login", "unknown"),
                    )
                    for item in items
                )
                if not items or page * self.GITHUB_PAGE_SIZE >= total_count:
                    break
        finally:
            self.delay = original_delay

        if not results and failure is None:
            return [self._row(
                "GitHub partial", url, "NOT FOUND", "no matching GitHub usernames found"
            )]

        if failure:
            coverage_detail = (
                f"Stopped after checking {len(results)} matching accounts across "
                f"{pages_checked} pages: {failure}."
            )
        elif total_count is not None and total_count > len(results):
            coverage_detail = (
                f"Showing {len(results)} of {total_count} matching accounts; "
                f"GitHub search results are limited to the first "
                f"{self.GITHUB_RESULT_LIMIT} accounts."
            )
        else:
            coverage_detail = ""

        if coverage_detail:
            results.append(self._row(
                "GitHub partial coverage",
                url,
                "COULD NOT CHECK",
                coverage_detail,
            ))
        return results

    def _check_bluesky_partial(self, target):
        url = "https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors"
        results = []
        cursor = None
        pages_checked = 0
        failure = None
        original_delay = self.delay
        try:
            self.delay = self.BLUESKY_SEARCH_DELAY
            while (
                len(results) < self.BLUESKY_RESULT_LIMIT
                and pages_checked < self.BLUESKY_PAGE_LIMIT
            ):
                params = {
                    "q": target,
                    "limit": min(
                        self.BLUESKY_PAGE_SIZE,
                        self.BLUESKY_RESULT_LIMIT - len(results),
                    ),
                }
                if cursor:
                    params["cursor"] = cursor
                response, err = self.safe_get(url, params=params)
                if err:
                    failure = f"request error: {err}"
                    break
                if response.status_code != 200:
                    failure = f"HTTP {response.status_code}"
                    break
                try:
                    payload = response.json()
                    actors = payload["actors"]
                    cursor = payload.get("cursor")
                except (ValueError, KeyError, TypeError, AttributeError):
                    failure = "invalid search response"
                    break

                if (
                    not isinstance(actors, list)
                    or not all(isinstance(actor, dict) for actor in actors)
                ):
                    failure = "invalid search response"
                    break
                if not actors:
                    break
                pages_checked += 1
                for actor in actors:
                    handle = actor.get("handle")
                    did = actor.get("did")
                    if not handle and not did:
                        continue
                    if not handle or handle == "handle.invalid":
                        profile_id = did
                        account_label = f"DID {did}"
                    else:
                        profile_id = handle
                        account_label = f"@{handle}"
                    profile_url = f"https://bsky.app/profile/{profile_id}"
                    display_name = actor.get("displayName")
                    detail = (
                        f"{display_name} ({account_label})"
                        if display_name
                        else account_label
                    )
                    results.append(self._row(
                        "Bluesky partial", profile_url, "FOUND", detail
                    ))
                if not cursor:
                    break
        finally:
            self.delay = original_delay

        if failure:
            results.append(self._row(
                "Bluesky partial coverage",
                url,
                "COULD NOT CHECK",
                f"Stopped after {pages_checked} pages and {len(results)} matches: {failure}.",
            ))
        elif cursor and (
            len(results) >= self.BLUESKY_RESULT_LIMIT
            or pages_checked >= self.BLUESKY_PAGE_LIMIT
        ):
            results.append(self._row(
                "Bluesky partial coverage",
                url,
                "COULD NOT CHECK",
                f"Stopped after {pages_checked} pages and {len(results)} matches; "
                "more results may exist.",
            ))
        elif not results:
            results.append(self._row(
                "Bluesky partial",
                url,
                "NOT FOUND",
                "No matching actors were returned by Bluesky public search.",
            ))
        return results

    def _check_codeberg_partial(self, target):
        url = "https://codeberg.org/api/v1/users/search"
        response, err = self.safe_get(
            url,
            params={"q": target, "limit": self.CODEBERG_RESULT_LIMIT},
        )
        if err:
            return [self._row(
                "Codeberg partial", url, "COULD NOT CHECK", f"request error: {err}"
            )]
        if response.status_code != 200:
            return [self._row(
                "Codeberg partial", url, "COULD NOT CHECK", f"HTTP {response.status_code}"
            )]
        try:
            payload = response.json()
            users = payload["data"]
        except (ValueError, KeyError, TypeError, AttributeError):
            return [self._row(
                "Codeberg partial", url, "COULD NOT CHECK", "invalid search response"
            )]
        if not isinstance(users, list) or not all(isinstance(user, dict) for user in users):
            return [self._row(
                "Codeberg partial", url, "COULD NOT CHECK", "invalid search response"
            )]
        if not users:
            return [self._row(
                "Codeberg partial", url, "NOT FOUND", "no matching users returned"
            )]

        results = []
        for user in users:
            login = user.get("login") or user.get("username")
            profile_url = user.get("html_url")
            if not login or not profile_url:
                continue
            detail = user.get("full_name") or login
            results.append(self._row(
                "Codeberg partial", profile_url, "FOUND", f"{detail} (@{login})"
            ))
        if not results:
            return [self._row(
                "Codeberg partial", url, "COULD NOT CHECK", "search results lacked usable profile data"
            )]
        if len(users) >= self.CODEBERG_RESULT_LIMIT:
            results.append(self._row(
                "Codeberg partial coverage",
                url,
                "COULD NOT CHECK",
                f"Received {len(users)} results; additional matching accounts may exist.",
            ))
        return results

    def _check_mastodon_partial(self, target):
        url = "https://mastodon.social/api/v2/search"
        response, err = self.safe_get(
            url,
            params={
                "q": target,
                "type": "accounts",
                "limit": self.MASTODON_RESULT_LIMIT,
            },
        )
        if err:
            return [self._row(
                "Mastodon partial", url, "COULD NOT CHECK", f"request error: {err}"
            )]
        if response.status_code != 200:
            return [self._row(
                "Mastodon partial", url, "COULD NOT CHECK", f"HTTP {response.status_code}"
            )]
        try:
            accounts = response.json()["accounts"]
        except (ValueError, KeyError, TypeError, AttributeError):
            return [self._row(
                "Mastodon partial", url, "COULD NOT CHECK", "invalid search response"
            )]
        if not isinstance(accounts, list) or not all(
            isinstance(account, dict) for account in accounts
        ):
            return [self._row(
                "Mastodon partial", url, "COULD NOT CHECK", "invalid search response"
            )]
        if not accounts:
            return [self._row(
                "Mastodon partial", url, "NOT FOUND",
                "no matching accounts returned by mastodon.social",
            )]

        results = []
        for account in accounts:
            profile_url = account.get("url")
            username = account.get("acct") or account.get("username")
            if not profile_url or not username:
                continue
            display_name = account.get("display_name")
            detail = (
                f"{display_name} (@{username})"
                if display_name
                else f"@{username}"
            )
            results.append(self._row(
                "Mastodon partial", profile_url, "FOUND", detail
            ))
        if not results:
            return [self._row(
                "Mastodon partial", url, "COULD NOT CHECK",
                "search results lacked usable profile data",
            )]
        if len(accounts) >= self.MASTODON_RESULT_LIMIT:
            results.append(self._row(
                "Mastodon partial coverage",
                url,
                "COULD NOT CHECK",
                f"Received {len(accounts)} results; additional matches may exist. "
                "Search is limited to accounts known to mastodon.social.",
            ))
        return results

    def run(self, target):
        results = []
        total = len(self.sites)

        for i, (site, (pattern, miss_text)) in enumerate(self.sites.items(), 1):
            print(f"      checking {i}/{total}: {site}", end="\r")
            if self.allow_partial and site == "GitHub":
                results.extend(self._check_github_partial(target))
            elif self.allow_partial and site == "Bluesky":
                results.extend(self._check_bluesky_partial(target))
            elif self.allow_partial and site == "Codeberg":
                results.extend(self._check_codeberg_partial(target))
            elif self.allow_partial and site == "Mastodon":
                results.extend(self._check_mastodon_partial(target))
            else:
                results.append(self._check_exact(site, pattern, miss_text, target))

        print(" " * 50, end="\r")
        return results