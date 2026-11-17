# Specter

Specter is a small, command-line OSINT learning project that checks public
sources for email, username, and phone-number traces. It reports per-source
results as **FOUND**, **NOT FOUND**, or **COULD NOT CHECK**.

Specter is not a people-finding service and does not claim complete coverage.
Use it only for information you own or are authorized to investigate.

## Requirements

- Python 3.11 or newer
- Internet access for public web/API checks

## Install and run

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

On Windows, activate the environment with `venv\Scripts\activate`.

Choose an option at the `specter>` prompt. Username lookup offers individual
platforms and an **ALL** option. Partial public account search is supported
for GitHub, Bluesky, Codeberg, and Mastodon; other platforms are exact-profile
checks. A selected search may return incomplete, ranked results subject to
that platform's coverage and limits.

Phone numbers are best entered in international format, including `+` and the
country calling code (for example, `+442071838750`). If you enter a national
number, Specter asks for the region used to parse it.

## Reports

After a lookup, Specter writes `output/report.md` and `output/results.json`.
These filenames are reused, so a later lookup replaces the previous report.
Reports can contain the queried email, username, or phone number; keep them
private and do not commit them to a public repository.

## What the checks mean

### Email

- Gravatar checks whether a public profile is associated with the email hash.
- XposedOrNot checks its available breach dataset and reports breach names,
  not leaked credentials.
- GitHub searches public account and commit data.
- Public web search may find pages mentioning the email, but it can be blocked
  and does not establish account registration.
- MX, SPF, and DMARC checks describe the email domain's mail configuration.
  They do not prove a mailbox exists or identify accounts.

No email check can produce a complete list of services where an address is
registered. Specter does not probe registration or password-reset forms.

### Username

Exact-profile checks only verify the requested profile URL and can be affected
by site behavior or blocks. Public partial-search support varies by platform:

- GitHub: public user search, limited by GitHub's result and rate limits.
- Bluesky: public actor search; matches may include profile text as well as
  handles.
- Codeberg: public account search; matches may include profile names.
- Mastodon: search through `mastodon.social`, limited to accounts known to that
  instance, not all accounts across the federated network.

Search suggestions are not proof that accounts belong to the same person.

### Phone

Phone results use the local `phonenumbers` numbering-plan metadata. They may
include number validity, country, approximate numbering-plan location, line
type, timezone, and an originally assigned carrier when metadata is available.
Carrier data may be outdated after number portability. This metadata cannot
identify the subscriber or provide a street address; Specter does not claim to
provide Truecaller-style identity or spam results.

## Privacy and ethics

Network checks send queries to the relevant public services. Email lookups send
the address to XposedOrNot, GitHub, and DuckDuckGo; Gravatar receives a hash,
and Google Public DNS receives the email domain. Phone lookup uses local
numbering metadata and does not send the phone number to a search engine.

Respect applicable laws, service terms, rate limits, and other people's
privacy. A timeout, block, malformed response, or unsupported check must not
be treated as proof that no result exists.

## Tests

Install the requirements, then run:

```bash
python -m pytest -q
```

The tests use mocked responses for web services and local phone metadata; they
do not make real account-registration probes.

## License

No license has been selected for this project yet. Choose one before publishing
if you want to specify how others may use, modify, and redistribute it.
