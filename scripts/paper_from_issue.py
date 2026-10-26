#!/usr/bin/env python3
"""Turn an "Add a paper" issue into a one-row CSV for import_papers.py.

Usage:
    python scripts/paper_from_issue.py <out.csv> <notes.md>

Reads the issue from the GitHub event payload ($GITHUB_EVENT_PATH), never from the command
line. Parses the issue-form fields (including the survey classification, whose options are generated
from config/taxonomy.json), then fills in title, authors, year and DOI from the arXiv
API (arXiv links) or Crossref (DOI links) when it can. Writes the row in the team CSV format
and a Markdown list of things the reviewer should check. Exits 1 if required fields are missing.
Standard library only.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from taxonomy import CLASS_COL, NOT_SURE, SUB_COL, load as load_taxonomy

FIELDS = ("paper_name,paper_link,code_link,year,authors,venue,publication_status,modality,task,loop_mechanism,"
          "model_name,doi,arxiv_id,project_link,code_status,official_code,verification_status,notes"
          ).split(",") + [CLASS_COL, SUB_COL, "classification_confidence"]
FORM = {  # issue-form heading -> key
    "Paper title": "title",
    "Paper link": "link",
    "Code link (if any)": "code",
    "Venue and year": "venue",
    "Imaging modality": "modality",
    "What is iterated?": "loop",
    "Survey classification": "classification",
    "Anything else?": "notes",
}
ATOM = "{http://www.w3.org/2005/Atom}"
UA = {"User-Agent": "awesome-looped-medical-bot (https://github.com/Big-Matrix-R-And-D-Lab/Awesome-Looped-Models-for-Medical-Imaging)"}


def parse_form(body: str) -> dict:
    out, key = {}, None
    for line in body.splitlines():
        m = re.match(r"^###\s+(.+?)\s*$", line)
        if m:
            key = FORM.get(m.group(1))
            if key:
                out[key] = []
            continue
        if key:
            out[key].append(line)
    clean = {k: "\n".join(v).strip() for k, v in out.items()}
    return {k: ("" if v == "_No response_" else v) for k, v in clean.items()}


def fetch(url: str, timeout: int = 20) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.read()
    except Exception as exc:  # noqa: BLE001 - enrichment is best effort
        print(f"note: could not fetch {url} ({exc})", file=sys.stderr)
        return None


def from_arxiv(link: str) -> dict:
    m = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", link)
    if not m:
        return {}
    data = fetch(f"https://export.arxiv.org/api/query?id_list={m.group(1)}")
    if not data:
        return {}
    entry = ET.fromstring(data).find(f"{ATOM}entry")
    if entry is None or entry.find(f"{ATOM}title") is None:
        return {}
    names = [" ".join((a.findtext(f"{ATOM}name") or "").split()) for a in entry.findall(f"{ATOM}author")]
    return {
        "title": " ".join((entry.findtext(f"{ATOM}title") or "").split()),
        "authors": "; ".join(n for n in names if n),
        "year": (entry.findtext(f"{ATOM}published") or "")[:4],
        "doi": f"10.48550/arXiv.{m.group(1)}",
        "source": "arXiv record",
    }


def from_crossref(link: str) -> dict:
    m = re.search(r"(10\.\d{4,9}/[^\s?#]+)", urllib.parse.unquote(link))
    if not m:
        return {}
    doi = m.group(1).rstrip(".")
    data = fetch(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='/')}")
    if not data:
        return {}
    msg = json.loads(data).get("message", {})
    names = [" ".join(f"{a.get('given', '')} {a.get('family', '')}".split()) for a in msg.get("author", [])]
    date = (msg.get("issued") or {}).get("date-parts") or [[None]]
    venue = (msg.get("container-title") or [""])[0]
    return {
        "title": " ".join(((msg.get("title") or [""])[0]).split()),
        "authors": "; ".join(n for n in names if n),
        "year": str(date[0][0] or ""),
        "doi": doi,
        "venue": venue,
        "source": "Crossref record",
    }


def model_name(title: str) -> tuple[str, bool]:
    head = title.split(":")[0].strip()
    if ":" in title and len(head) <= 40:
        return head, False
    return " ".join(title.split()[:4]), True


def main() -> int:
    out_csv, out_notes = Path(sys.argv[1]), Path(sys.argv[2])
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    number, login = issue.get("number"), (issue.get("user") or {}).get("login", "")
    f = parse_form(issue.get("body") or "")

    if not f.get("title") or not f.get("link", "").startswith(("http://", "https://")):
        print("The issue needs a paper title and a full http(s) paper link.", file=sys.stderr)
        return 1

    meta = from_arxiv(f["link"]) or from_crossref(f["link"])
    checks = []
    title = meta.get("title") or f["title"]
    if meta.get("title") and meta["title"].lower() != f["title"].lower():
        checks.append(f"Title taken from the {meta['source']} (the issue said *{f['title']}*).")
    year = meta.get("year") or (re.search(r"\b(19|20)\d\d\b", f.get("venue", "")) or [""])[0]
    if not year:
        checks.append("No year found: set `year` before merging.")
    venue = re.sub(r"\s*\b(19|20)\d\d\b", "", f.get("venue", "")).strip() or meta.get("venue", "")
    if not venue and "arxiv" in f["link"]:
        venue = "arXiv preprint"
    model, guessed = model_name(title)
    if guessed:
        checks.append(f"Model name guessed as **{model}**: shorten it if the paper uses a name.")
    # The form only offers approved "Class > Subcategory" pairs; anything else (including "Not sure"
    # and issues opened with an older form) is left empty so import_papers.py flags it for review.
    tax = load_taxonomy()
    chosen = f.get("classification", "").strip()
    cls, sub = tax.parse_label(chosen) if chosen and chosen != NOT_SURE else (None, None)
    if not (cls and sub and tax.is_valid(cls, sub)):
        cls, sub = "", ""
        checks.append("No survey classification chosen: a maintainer must pick one before this can be added.")
    code = f.get("code", "")
    if code:
        checks.append("Code link came from the issue: confirm it is the authors' repository and set `code_status` "
                      "to where it is linked from (see CONTRIBUTING.md).")
    if not meta:
        checks.append("Could not read the paper's metadata automatically: add `authors` and check the venue.")

    row = {k: "" for k in FIELDS}
    row.update({
        "paper_name": title,
        "paper_link": f["link"],
        "code_link": code,
        "year": year,
        "authors": meta.get("authors", ""),
        "venue": venue,
        "modality": f.get("modality", ""),
        "loop_mechanism": f.get("loop", ""),
        "publication_status": "Preprint" if "arxiv" in f["link"].lower() else "",
        "model_name": model,
        "doi": meta.get("doi", ""),
        "arxiv_id": (re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", f["link"]) or [None, ""])[1],
        "code_status": "Code link supplied in the issue" if code else "No project-specific URL found",
        "official_code": "Yes" if code else "No",
        CLASS_COL: cls,
        SUB_COL: sub,
        "classification_confidence": "",
        "verification_status": f"From issue #{number}" + (f"; metadata from the {meta['source']}" if meta else ""),
        "notes": f"Suggested in issue #{number} by @{login}." + (f" {f['notes'][:400]}" if f.get("notes") else ""),
    })
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerow(row)
    out_notes.write_text("".join(f"- {c}\n" for c in checks), encoding="utf-8")
    print(f"Prepared row for {model} ({year}); {len(checks)} checks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
