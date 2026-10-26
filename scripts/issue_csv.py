#!/usr/bin/env python3
"""Find the CSV in a bulk-import issue (used by .github/workflows/bulk-import.yml).

Usage:
    python scripts/issue_csv.py <out.csv>

Reads the issue body from the GitHub event payload ($GITHUB_EVENT_PATH), never from the
command line, so issue text cannot reach the shell. Then either:
  - finds an attached .csv (a GitHub attachment link) and prints `url=<link>` to $GITHUB_OUTPUT
    for the workflow to download, or
  - finds CSV text pasted into the issue, writes it to <out.csv> and prints `inline=true`.
Exits 1 with a message when neither is found. Standard library only.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# GitHub's own attachment hosts. Links anywhere else are ignored.
ALLOWED = [
    ("github.com", re.compile(r"^/user-attachments/files/\d+/[^/]+\.csv$", re.I)),
    ("github.com", re.compile(r"^/[^/]+/[^/]+/files/\d+/[^/]+\.csv$", re.I)),
]
LINK = re.compile(r"\((https://[^)\s]+\.csv)\)|<(https://[^>\s]+\.csv)>|(https://\S+\.csv)\b", re.I)


def output(**pairs: str) -> None:
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a", encoding="utf-8") as f:
        for k, v in pairs.items():
            f.write(f"{k}={v}\n")


def attachment_url(body: str) -> str | None:
    for m in LINK.finditer(body):
        url = next(g for g in m.groups() if g)
        u = urlparse(url)
        if any(u.hostname == host and pat.match(u.path) for host, pat in ALLOWED):
            return url
    return None


def pasted_csv(body: str) -> str | None:
    fenced = re.search(r"```[a-z]*\n(.*?)```", body, re.S)
    text = fenced.group(1) if fenced else body
    start = text.find("paper_name,")
    if start == -1:
        return None
    text = text[start:]
    nxt = re.search(r"^### ", text, re.M)  # issue forms put the next field's heading after the CSV
    return (text[: nxt.start()] if nxt else text).strip() + "\n"


def main() -> int:
    out = Path(sys.argv[1])
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    body = (event.get("issue") or {}).get("body") or ""

    url = attachment_url(body)
    if url:
        output(url=url)
        print(f"Found attachment: {url}")
        return 0
    text = pasted_csv(body)
    if text:
        out.write_text(text, encoding="utf-8")
        output(inline="true")
        print(f"Found pasted CSV ({text.count(chr(10))} lines)")
        return 0
    print("No CSV attachment or pasted CSV found in the issue.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
