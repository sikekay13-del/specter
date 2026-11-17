from types import SimpleNamespace

from modules.social import SocialModule


def test_github_partial_search_finds_match_on_later_page():
    requested_pages = []

    def safe_get(url, **kwargs):
        params = kwargs["params"]
        requested_pages.append(params)
        items = [
            {
                "login": f"example-{params['page']}-{index}",
                "html_url": f"https://github.com/example-{params['page']}-{index}",
            }
            for index in range(100)
        ]
        if params["page"] == 5:
            items[4] = {
                "login": "sikekay13-del",
                "html_url": "https://github.com/sikekay13-del",
            }
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"total_count": 500, "items": items},
        ), None

    module = SocialModule(
        sites={"GitHub": ("https://github.com/{}", None)},
        allow_partial=True,
    )
    module.safe_get = safe_get

    results = module.run("sike")

    assert [params["page"] for params in requested_pages] == [1, 2, 3, 4, 5]
    assert all(params["q"] == "sike in:login" for params in requested_pages)
    assert all(params["per_page"] == 100 for params in requested_pages)
    assert any(result["detail"] == "sikekay13-del" for result in results)
    assert len(results) == 500


def test_github_partial_search_reports_api_result_cap():
    module = SocialModule(
        sites={"GitHub": ("https://github.com/{}", None)},
        allow_partial=True,
    )

    def safe_get(url, **kwargs):
        page = kwargs["params"]["page"]
        items = [
            {
                "login": f"sike-user-{page}-{index}",
                "html_url": f"https://github.com/sike-user-{page}-{index}",
            }
            for index in range(100)
        ]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"total_count": 1250, "items": items},
        ), None

    module.safe_get = safe_get

    results = module.run("sike")

    assert len(results) == 1001
    assert results[-1]["state"] == "COULD NOT CHECK"
    assert "Showing 1000 of 1250" in results[-1]["detail"]


def test_bluesky_partial_search_returns_multiple_accounts_and_follows_cursor():
    requested = []
    responses = [
        {
            "actors": [
                {"handle": "sike.one", "displayName": "Sike One"},
                {"handle": "sike.two"},
            ],
            "cursor": "next-page",
        },
        {
            "actors": [
                {"handle": "sike.three", "displayName": "Sike Three"},
                {
                    "handle": "handle.invalid",
                    "did": "did:plc:example",
                    "displayName": "Former account",
                },
            ],
        },
    ]

    def safe_get(url, **kwargs):
        requested.append((url, kwargs["params"]))
        payload = responses[len(requested) - 1]
        return SimpleNamespace(status_code=200, json=lambda: payload), None

    module = SocialModule(
        sites={"Bluesky": ("https://bsky.app/profile/{}", None)},
        allow_partial=True,
    )
    module.safe_get = safe_get

    results = module.run("sike")

    assert len(results) == 4
    assert [result["detail"] for result in results] == [
        "Sike One (@sike.one)",
        "@sike.two",
        "Sike Three (@sike.three)",
        "Former account (DID did:plc:example)",
    ]
    assert all(result["state"] == "FOUND" for result in results)
    assert results[-1]["url"] == "https://bsky.app/profile/did:plc:example"
    assert requested[0][1] == {"q": "sike", "limit": 100}
    assert requested[1][1] == {"q": "sike", "limit": 100, "cursor": "next-page"}


def test_all_platforms_use_partial_search_only_where_supported():
    sites = {
        "GitHub": ("https://github.com/{}", None),
        "Bluesky": ("https://bsky.app/profile/{}", None),
        "Codeberg": ("https://codeberg.org/{}", None),
        "Mastodon": ("https://mastodon.social/@{}", None),
        "Other": ("https://example.test/{}", None),
    }
    module = SocialModule(sites=sites, allow_partial=True)
    module._check_github_partial = lambda target: [
        module._row("GitHub partial", "https://github.com/sike", "FOUND", "sike")
    ]
    module._check_bluesky_partial = lambda target: [
        module._row("Bluesky partial", "https://bsky.app/profile/sike", "FOUND", "@sike")
    ]
    module._check_codeberg_partial = lambda target: [
        module._row("Codeberg partial", "https://codeberg.org/sike", "FOUND", "@sike")
    ]
    module._check_mastodon_partial = lambda target: [
        module._row("Mastodon partial", "https://mastodon.social/@sike", "FOUND", "@sike")
    ]
    module._check_exact = lambda site, pattern, miss_text, target: module._row(
        site, pattern.format(target), "FOUND", "exact check"
    )

    results = module.run("sike")

    assert [result["source"] for result in results] == [
        "GitHub partial",
        "Bluesky partial",
        "Codeberg partial",
        "Mastodon partial",
        "Other",
    ]


def test_codeberg_partial_search_returns_multiple_accounts():
    module = SocialModule(
        sites={"Codeberg": ("https://codeberg.org/{}", None)},
        allow_partial=True,
    )
    module.safe_get = lambda *args, **kwargs: (
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "data": [
                    {
                        "login": "corcoran06",
                        "full_name": "Corcoran",
                        "html_url": "https://codeberg.org/corcoran06",
                    },
                    {
                        "login": "corcoran",
                        "full_name": "",
                        "html_url": "https://codeberg.org/corcoran",
                    },
                ]
            },
        ),
        None,
    )

    results = module.run("corcoran")

    assert [row["detail"] for row in results] == [
        "Corcoran (@corcoran06)",
        "corcoran (@corcoran)",
    ]
    assert all(row["state"] == "FOUND" for row in results)


def test_mastodon_partial_search_returns_multiple_accounts():
    module = SocialModule(
        sites={"Mastodon": ("https://mastodon.social/@{}", None)},
        allow_partial=True,
    )
    module.safe_get = lambda *args, **kwargs: (
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "accounts": [
                    {
                        "acct": "corcoran06",
                        "username": "corcoran06",
                        "display_name": "Corcoran",
                        "url": "https://mastodon.online/@corcoran06",
                    },
                    {
                        "acct": "corcoran@other.social",
                        "username": "corcoran",
                        "display_name": "",
                        "url": "https://other.social/@corcoran",
                    },
                ]
            },
        ),
        None,
    )

    results = module.run("corcoran")

    assert [row["detail"] for row in results] == [
        "Corcoran (@corcoran06)",
        "@corcoran@other.social",
    ]
    assert all(row["state"] == "FOUND" for row in results)
