from .base import BaseScraper


class CodeModule(BaseScraper):
    name = "github"
    supports = ["email"]

    API = "https://api.github.com/search"

    def _row(self, source, url, state, detail):
        return {
            "source": source,
            "url": url,
            "state": state,
            "found": state == "FOUND",
            "detail": detail,
        }

    def _search(self, endpoint, query, source):
        response, err = self.safe_get(
            f"{self.API}/{endpoint}",
            params={"q": query, "per_page": 10},
        )
        if err:
            return None, self._row(
                source, "", "COULD NOT CHECK", f"request error: {err}"
            )
        if response.status_code != 200:
            return None, self._row(
                source, "", "COULD NOT CHECK", f"HTTP {response.status_code}"
            )
        try:
            payload = response.json()
            items = payload["items"]
        except (ValueError, KeyError, TypeError, AttributeError):
            return None, self._row(
                source, "", "COULD NOT CHECK", "invalid GitHub search response"
            )
        if not isinstance(items, list) or not all(
            isinstance(item, dict) for item in items
        ):
            return None, self._row(
                source, "", "COULD NOT CHECK", "invalid GitHub search response"
            )
        return items, None

    def run(self, target):
        results = []

        users, error = self._search(
            "users", f"{target} in:email", "GitHub public account"
        )
        if error:
            results.append(error)
        elif not users:
            results.append(self._row(
                "GitHub public account",
                "",
                "NOT FOUND",
                "No public GitHub account email match was returned.",
            ))
        else:
            for user in users:
                login = user.get("login")
                profile_url = user.get("html_url")
                if not login or not profile_url:
                    results.append(self._row(
                        "GitHub public account",
                        "",
                        "COULD NOT CHECK",
                        "GitHub returned an account without usable profile details.",
                    ))
                    continue
                results.append(self._row(
                    "GitHub public account",
                    profile_url,
                    "FOUND",
                    f"Public email match: {login}",
                ))

        commits, error = self._search(
            "commits",
            f"author-email:{target}",
            "GitHub public commit",
        )
        if error:
            results.append(error)
        else:
            seen = set()
            for commit in commits:
                repository = commit.get("repository") or {}
                if not isinstance(repository, dict):
                    continue
                full_name = repository.get("full_name")
                if not full_name or full_name in seen:
                    continue
                seen.add(full_name)
                repo_url = repository.get("html_url")
                if not repo_url:
                    results.append(self._row(
                        "GitHub public commit",
                        "",
                        "COULD NOT CHECK",
                        "GitHub returned a repository without a usable URL.",
                    ))
                    continue
                results.append(self._row(
                    "GitHub public commit",
                    repo_url,
                    "FOUND",
                    f"Public commit search matched repository {full_name}.",
                ))
            if not seen:
                results.append(self._row(
                    "GitHub public commit",
                    "",
                    "NOT FOUND",
                    "No public commits matching the email were returned.",
                ))
        return results
