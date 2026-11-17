import json
import os
from datetime import datetime
import pandas as pd

RESULT_STATES = {"FOUND", "NOT FOUND", "COULD NOT CHECK"}
MARKDOWN_SPECIALS = set(r"\`*_{}[]()#+-.!|>")


def _escape_markdown(value):
    """Keep untrusted target/result text from changing the report structure."""
    text = " ".join(str(value).replace("\r", " ").replace("\n", " ").split())
    return "".join(f"\\{char}" if char in MARKDOWN_SPECIALS else char for char in text)


def build_dataframe(results):
    """Turn the list of dicts from the modules into a DataFrame."""
    rows = []
    for result in results:
        state = result.get("state")
        if state is None:
            state = "FOUND" if result.get("found", False) else "NOT FOUND"
        if state not in RESULT_STATES:
            raise ValueError(f"Unsupported result state: {state}")
        rows.append({
            "source": result.get("source", ""),
            "url": result.get("url", ""),
            "state": state,
            "detail": result.get("detail", ""),
        })
    return pd.DataFrame(rows, columns=["source", "url", "state", "detail"])


def write_json(df, target, target_type, out_dir):
    data = {
        "target": target,
        "type": target_type,
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "total_checked": len(df),
        "total_found": int((df["state"] == "FOUND").sum()),
        "total_not_found": int((df["state"] == "NOT FOUND").sum()),
        "total_could_not_check": int((df["state"] == "COULD NOT CHECK").sum()),
        "results": df.to_dict(orient="records"),
    }
    path = os.path.join(out_dir, "results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def write_markdown(df, target, target_type, out_dir):
    lines = [
        "# Specter Report",
        "",
        f"- **Target:** {_escape_markdown(target)} ({target_type})",
        f"- **Scanned:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Checked:** {len(df)}"
        f" | **Found:** {(df['state'] == 'FOUND').sum()}"
        f" | **Not found:** {(df['state'] == 'NOT FOUND').sum()}"
        f" | **Could not check:** {(df['state'] == 'COULD NOT CHECK').sum()}",
    ]

    if target_type == "email":
        lines += [
            "",
            "## Scope and limitations",
            "",
            "This is a partial public-footprint and exposure check, not a list of "
            "accounts registered to the email address.",
            "",
            "- A missing result means only that the named source returned no match.",
            "- Domain MX, SPF, and DMARC records describe mail configuration; "
            "they do not verify a mailbox or account.",
            "- Breach results reflect the breach provider's available dataset. "
            "No breach match does not prove the address has never been exposed.",
            "- Public search coverage is incomplete and may be blocked or rate-limited.",
            "- No signup or password-reset forms are queried.",
        ]

    for state in ("FOUND", "NOT FOUND", "COULD NOT CHECK"):
        matching = df[df["state"] == state]
        lines += ["", f"## {state.title()}", ""]
        if matching.empty:
            lines.append("_None._")
        else:
            lines += ["| Source | URL | Detail |", "|---|---|---|"]
            for _, row in matching.iterrows():
                lines.append(
                    f"| {_escape_markdown(row['source'])} "
                    f"| {_escape_markdown(row['url'])} "
                    f"| {_escape_markdown(row['detail'])} |"
                )

    path = os.path.join(out_dir, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path