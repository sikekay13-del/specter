from types import SimpleNamespace
from pathlib import Path

from modules.mail import EmailModule
from modules.reporter import build_dataframe, write_markdown


def response(status_code, payload=None):
    return SimpleNamespace(
        status_code=status_code,
        json=lambda: payload,
    )


def test_breach_lookup_encodes_email_and_handles_provider_not_found():
    module = EmailModule()
    requested = []

    def safe_get(url):
        requested.append(url)
        return response(200, {"Error": "Not found", "email": None}), None

    module.safe_get = safe_get

    result = module._breaches("user+tag@example.com")

    assert requested == [
        "https://api.xposedornot.com/v1/check-email/user%2Btag%40example.com"
    ]
    assert result["state"] == "NOT FOUND"
    assert "No breach matches" in result["detail"]


def test_breach_lookup_reports_matches_without_exposing_leaked_data():
    module = EmailModule()

    def safe_get(url):
        assert url.startswith("https://api.xposedornot.com/")
        return response(200, {"breaches": [["ExampleLeak", "AnotherLeak"]]}), None

    module.safe_get = safe_get

    result = module._breaches("user@example.com")

    assert result["state"] == "FOUND"
    assert "ExampleLeak, AnotherLeak" in result["detail"]
    assert "password" not in result["detail"].lower()


def test_domain_mail_checks_report_mx_spf_and_dmarc_records():
    module = EmailModule()
    requests = []

    def safe_get(url, **kwargs):
        assert url == module.DNS_URL
        params = kwargs["params"]
        requests.append(params)
        name, record_type = params["name"], params["type"]
        if record_type == "MX":
            payload = {"Status": 0, "Answer": [{"data": "10 mail.example.com."}]}
        elif name == "example.com":
            payload = {
                "Status": 0,
                "Answer": [
                    {"data": "v=spf1 -all"},
                    {"data": "verification=abc"},
                ],
            }
        else:
            payload = {
                "Status": 0,
                "Answer": [{"data": "v=DMARC1; p=reject"}],
            }
        return response(200, payload), None

    module.safe_get = safe_get
    results = module._domain_mail_records("user@example.com")

    assert [row["source"] for row in results] == [
        "Domain MX", "Domain SPF", "Domain DMARC"
    ]
    assert all(row["state"] == "FOUND" for row in results)
    assert "mail.example.com" in results[0]["detail"]
    assert "v=spf1" in results[1]["detail"]
    assert "v=DMARC1" in results[2]["detail"]
    assert requests == [
        {"name": "example.com", "type": "MX"},
        {"name": "example.com", "type": "TXT"},
        {"name": "_dmarc.example.com", "type": "TXT"},
    ]


def test_dns_errors_are_could_not_check_not_not_found():
    module = EmailModule()

    def safe_get(url, **kwargs):
        assert url == module.DNS_URL
        assert kwargs["params"]["type"] in {"MX", "TXT"}
        return None, "timeout"

    module.safe_get = safe_get

    results = module._domain_mail_records("user@example.com")

    assert len(results) == 3
    assert all(row["state"] == "COULD NOT CHECK" for row in results)


def test_email_report_explains_partial_scope(tmp_path):
    df = build_dataframe([
        {
            "source": "Domain SPF",
            "url": "https://dns.google/resolve",
            "state": "FOUND",
            "detail": "v=spf1 -all",
        }
    ])

    report_path = write_markdown(df, "user@example.com", "email", str(tmp_path))
    report = Path(report_path).read_text(encoding="utf-8")

    assert "not a list of accounts registered" in report
    assert "do not verify a mailbox or account" in report
    assert "No signup or password-reset forms are queried." in report


def test_markdown_report_escapes_untrusted_table_content(tmp_path):
    df = build_dataframe([
        {
            "source": "site|[link]",
            "url": "https://example.test/",
            "state": "FOUND",
            "detail": "first line\n|second line|",
        }
    ])

    report_path = write_markdown(
        df, "target|[example]", "username", str(tmp_path)
    )
    report = Path(report_path).read_text(encoding="utf-8")

    assert r"target\|\[example\]" in report
    assert r"site\|\[link\]" in report
    assert r"first line \|second line\|" in report
