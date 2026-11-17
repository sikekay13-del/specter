import hashlib
from urllib.parse import quote

from .base import BaseScraper


class EmailModule(BaseScraper):
    name = "email"
    supports = ["email"]
    delay = 2.0
    DNS_URL = "https://dns.google/resolve"

    def _row(self, source, url, state, detail):
        return {
            "source": source,
            "url": url,
            "state": state,
            "found": state == "FOUND",
            "detail": detail,
        }

    def _gravatar(self, email):
        h = hashlib.md5(email.strip().lower().encode()).hexdigest()
        r, err = self.safe_get(f"https://en.gravatar.com/{h}.json")
        if err:
            return self._row("Gravatar", "", "COULD NOT CHECK", f"error: {err}")
        if r.status_code == 200:
            try:
                entries = r.json()["entry"]
                if not isinstance(entries, list):
                    raise ValueError("unexpected Gravatar response")
                if not entries:
                    return self._row(
                        "Gravatar", "", "NOT FOUND", "no public profile"
                    )
                if not isinstance(entries[0], dict):
                    raise ValueError("unexpected Gravatar profile")
                name = entries[0].get("displayName", "")
            except (ValueError, KeyError, TypeError):
                return self._row(
                    "Gravatar", "", "COULD NOT CHECK", "invalid profile response"
                )
            if name:
                return self._row("Gravatar", f"https://gravatar.com/{h}", "FOUND", name)
            return self._row("Gravatar", f"https://gravatar.com/{h}", "NOT FOUND", "no public profile")
        if r.status_code == 404:
            return self._row("Gravatar", "", "NOT FOUND", "no profile")
        return self._row("Gravatar", "", "COULD NOT CHECK", f"HTTP {r.status_code}")

    def _breaches(self, email):
        encoded_email = quote(email.strip(), safe="")
        url = f"https://api.xposedornot.com/v1/check-email/{encoded_email}"
        r, err = self.safe_get(url)
        if err:
            return self._row("Breach check", "", "COULD NOT CHECK", f"error: {err}")
        if r.status_code == 200:
            try:
                payload = r.json()
                if "Error" in payload and str(payload["Error"]).lower() == "not found":
                    return self._row(
                        "Breach exposure",
                        "https://xposedornot.com/",
                        "NOT FOUND",
                        "No breach matches were returned by XposedOrNot.",
                    )
                breach_groups = payload["breaches"]
                if (
                    not isinstance(breach_groups, list)
                    or not breach_groups
                    or not isinstance(breach_groups[0], list)
                    or not all(isinstance(name, str) for name in breach_groups[0])
                ):
                    raise ValueError("unexpected breach response")
                names = breach_groups[0]
            except (ValueError, KeyError, TypeError, AttributeError):
                return self._row(
                    "Breach exposure", "https://xposedornot.com/",
                    "COULD NOT CHECK", "invalid breach-search response",
                )
            if names:
                return self._row(
                    "Breach exposure",
                    "https://xposedornot.com/",
                    "FOUND",
                    f"{len(names)} breaches: " + ", ".join(names[:8]),
                )
            return self._row(
                "Breach exposure", "https://xposedornot.com/",
                "NOT FOUND", "No breach matches were returned by XposedOrNot.",
            )
        if r.status_code == 404:
            return self._row(
                "Breach exposure", "https://xposedornot.com/",
                "NOT FOUND", "No breach matches were returned by XposedOrNot.",
            )
        return self._row(
            "Breach exposure", "https://xposedornot.com/",
            "COULD NOT CHECK", f"HTTP {r.status_code}",
        )

    def _domain_record(self, domain, record_type, name=None):
        query_name = f"{name}.{domain}" if name else domain
        url = f"{self.DNS_URL}?name={quote(query_name, safe='')}&type={record_type}"
        response, err = self.safe_get(
            self.DNS_URL,
            params={"name": query_name, "type": record_type},
        )
        label = {
            ("MX", None): "Domain MX",
            ("TXT", None): "Domain SPF",
            ("TXT", "_dmarc"): "Domain DMARC",
        }[(record_type, name)]
        if err:
            return self._row(label, url, "COULD NOT CHECK", f"DNS lookup failed: {err}")
        if response.status_code != 200:
            return self._row(
                label, url, "COULD NOT CHECK", f"DNS resolver HTTP {response.status_code}"
            )
        try:
            payload = response.json()
            status = payload["Status"]
            if not isinstance(status, int):
                raise ValueError("invalid DNS status")
            if status not in {0, 3}:
                return self._row(
                    label, url, "COULD NOT CHECK",
                    f"DNS resolver returned status {status}",
                )
            answers = payload.get("Answer", [])
            if not isinstance(answers, list) or not all(
                isinstance(answer, dict) for answer in answers
            ):
                raise ValueError("invalid DNS answer")
            values = [answer.get("data") for answer in answers]
            values = [value for value in values if isinstance(value, str)]
        except (ValueError, KeyError, TypeError, AttributeError):
            return self._row(
                label, url, "COULD NOT CHECK", "invalid DNS resolver response"
            )

        if record_type == "TXT":
            if name == "_dmarc":
                values = [value for value in values if value.lower().startswith("v=dmarc1")]
            else:
                values = [value for value in values if value.lower().startswith("v=spf1")]
        if not values:
            return self._row(
                label, url, "NOT FOUND",
                f"No {record_type} record of the requested type was returned for {query_name}.",
            )
        return self._row(
            label, url, "FOUND", "; ".join(value[:300] for value in values[:5])
        )

    def _domain_mail_records(self, email):
        domain = email.rsplit("@", 1)[1].strip().rstrip(".")
        try:
            domain = domain.encode("idna").decode("ascii")
        except UnicodeError:
            return [self._row(
                "Domain mail records", "", "COULD NOT CHECK",
                "Could not convert the email domain to a DNS name.",
            )]
        return [
            self._domain_record(domain, "MX"),
            self._domain_record(domain, "TXT"),
            self._domain_record(domain, "TXT", "_dmarc"),
        ]

    def run(self, target):
        return [
            self._gravatar(target),
            self._breaches(target),
            *self._domain_mail_records(target),
        ]