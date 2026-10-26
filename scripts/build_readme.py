#!/usr/bin/env python3
"""Generate README.md from data/papers.csv, grouped by the closed survey taxonomy.

Grouping and order come only from config/taxonomy.json. A class or subcategory that is not in
the taxonomy is a validation error; it is never appended to the page.

Usage:
    python scripts/build_readme.py           # validate the CSV and rewrite README.md
    python scripts/build_readme.py --check   # validate and fail if README.md is out of date

Only the Python standard library is used, so no installation is needed.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from collections import Counter
from pathlib import Path

from taxonomy import CLASS_COL, SUB_COL, load as load_taxonomy

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "papers.csv"
README_PATH = ROOT / "README.md"
TEMPLATES = Path(__file__).resolve().parent / "templates"

QUEUE_PATH = ROOT / "data" / "review_queue.csv"

# Canonical column schema of data/papers.csv. The survey classification is stored in exactly two
# columns (taxonomy_class + taxonomy_subcategory). The raw curation label of the source record is kept
# in `source_primary_category` for traceability only: it never decides a heading (the manuscript maps
# its 36 raw labels onto the families in Supplementary Table S1, with one row-level override).
FIELDS = [
    "paper_name", "paper_link", "code_link", "year", "authors", "venue", "venue_short", "publication_status",
    CLASS_COL, SUB_COL, "classification_confidence", "model_name", "source_primary_category",
    "loop_mechanism", "loop_level", "modality", "task", "methodology_summary", "dataset", "evaluation_metrics",
    "stability_evidence", "external_validation", "doi", "arxiv_id", "project_link", "code_status",
    "official_code", "survey_ref", "context_level", "verification_status", "notes", "suggested_by",
]
QUEUE_FIELDS = FIELDS + ["review_reason"]
# Column names that would carry a second, independently editable classification into the table.
LEGACY_FIELDS = {"section", "inclusion_type", "primary_category", "loop_family"}
REQUIRED = ["paper_name", "paper_link", "year", "model_name", CLASS_COL, SUB_COL]
CONFIDENCE = {"", "high", "medium", "low"}
PUBLICATION_STATUS = {"", "Published", "Accepted", "Preprint"}
LOOP_LEVELS = {"", "L1", "L2", "L3", "L4"}
FOLLOW_UP = "Survey follow-up link (Table S10)"
CODE_STATUS = {
    "",
    "Linked from the official paper page",
    "Curated record",
    FOLLOW_UP,
    "Repository without method code (Table S10)",
    "Project page only",
    "No project-specific URL found",
    "Code link supplied in the issue",
}
GITHUB_RE = re.compile(r"^https?://github\.com/([^/\s]+)/([^/\s#?]+)")


# --------------------------------------------------------------------------- data
def load_table(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
        return [(c or "").strip() for c in reader.fieldnames or []], rows


def load_rows() -> list[dict]:
    return load_table(CSV_PATH)[1]


def title_key(title: str) -> str:
    return re.sub(r"\W+", " ", (title or "").lower()).strip()


def check_header(fields: list[str], expected: list[str], name: str) -> list[str]:
    errors = []
    legacy = sorted(LEGACY_FIELDS & set(fields))
    if legacy:
        errors.append(f"{name}: legacy column(s) {legacy} are not allowed; the classification lives in "
                      f"`{CLASS_COL}` + `{SUB_COL}` (see config/taxonomy.json)")
    missing = [c for c in expected if c not in fields]
    unknown = [c for c in fields if c not in expected and c not in LEGACY_FIELDS]
    if missing:
        errors.append(f"{name}: missing column(s) {missing}")
    if unknown:
        errors.append(f"{name}: unknown column(s) {unknown}")
    return errors


def check_metadata(r: dict, where: str) -> list[str]:
    """Rules shared by published rows and review-queue rows (everything except the taxonomy)."""
    errors = []
    for col in ("paper_name", "paper_link", "year", "model_name"):
        if not r.get(col):
            errors.append(f"{where}: missing required field '{col}'")
    if r.get("year") and not re.fullmatch(r"(19|20)\d\d", r["year"]):
        errors.append(f"{where}: year '{r['year']}' is not a 4-digit year")
    for col in ("paper_link", "code_link", "project_link", "dataset_link"):
        if r.get(col) and not r[col].startswith(("http://", "https://")):
            errors.append(f"{where}: {col} must be a full http(s) URL")
    if r.get("official_code") not in ("", "Yes", "No", None):
        errors.append(f"{where}: official_code must be 'Yes', 'No' or empty")
    if r.get("official_code") == "Yes" and not r.get("code_link"):
        errors.append(f"{where}: official_code is 'Yes' but code_link is empty")
    if r.get("classification_confidence", "") not in CONFIDENCE:
        errors.append(f"{where}: classification_confidence must be high, medium, low or empty")
    if r.get("publication_status", "") not in PUBLICATION_STATUS:
        errors.append(f"{where}: publication_status must be Published, Accepted, Preprint or empty")
    if r.get("loop_level", "") not in LOOP_LEVELS:
        errors.append(f"{where}: loop_level must be L1, L2, L3, L4 or empty")
    if r.get("code_status", "") not in CODE_STATUS:
        errors.append(f"{where}: code_status '{r['code_status']}' is not one of {sorted(CODE_STATUS - {''})}")
    if r.get("official_code") == "Yes" and r.get("code_status") not in (
            "Linked from the official paper page", "Curated record", "Code link supplied in the issue"):
        errors.append(f"{where}: official_code 'Yes' needs a code_status showing where the link came from")
    if r.get("context_level") not in ("", "Yes", None):
        errors.append(f"{where}: context_level must be 'Yes' or empty")
    if r.get("survey_ref") and not re.fullmatch(r"\[\d+\]", r["survey_ref"]):
        errors.append(f"{where}: survey_ref must look like [24]")
    return errors


def validate(rows: list[dict], name: str = "data/papers.csv") -> list[str]:
    """Published rows: metadata rules plus a closed-taxonomy check. Unknown classes or
    subcategories are errors, never new sections."""
    tax = load_taxonomy()
    errors: list[str] = []
    seen_titles: dict[str, int] = {}
    for n, r in enumerate(rows, start=2):  # line 1 is the header
        where = f"{name} line {n}"
        errors += check_metadata(r, where)
        problem = tax.check(r.get(CLASS_COL, ""), r.get(SUB_COL, ""))
        if problem:
            errors.append(f"{where}: {problem}. Use an approved classification from config/taxonomy.json, "
                          f"or move the paper to data/review_queue.csv")
        if r.get("classification_confidence") == "low":
            errors.append(f"{where}: low-confidence classifications cannot be published; move it to data/review_queue.csv")
        key = title_key(r.get("paper_name", ""))
        if key in seen_titles:
            errors.append(f"{where}: duplicate of the paper on line {seen_titles[key]}")
        elif key:
            seen_titles[key] = n
    return errors


def validate_queue(rows: list[dict], published: list[dict]) -> list[str]:
    """Review-queue rows keep full metadata; a classification there is optional but, if present,
    must still be an approved pair. No paper may be both queued and published."""
    tax = load_taxonomy()
    errors: list[str] = []
    pub = {title_key(r["paper_name"]) for r in published}
    pub_links = {r["paper_link"].rstrip("/") for r in published if r.get("paper_link")}
    seen: dict[str, int] = {}
    for n, r in enumerate(rows, start=2):
        where = f"data/review_queue.csv line {n}"
        errors += check_metadata(r, where)
        if not r.get("review_reason"):
            errors.append(f"{where}: review_reason is required")
        if r.get(CLASS_COL) or r.get(SUB_COL):
            problem = tax.check(r.get(CLASS_COL, ""), r.get(SUB_COL, ""))
            if problem:
                errors.append(f"{where}: {problem}")
        key = title_key(r.get("paper_name", ""))
        if key in pub or r.get("paper_link", "").rstrip("/") in pub_links:
            errors.append(f"{where}: this paper is also in data/papers.csv; keep it in one file only")
        if key in seen:
            errors.append(f"{where}: duplicate of the queued paper on line {seen[key]}")
        elif key:
            seen[key] = n
    return errors


def validate_all() -> list[str]:
    """Everything CI checks about the data files."""
    fields, rows = load_table(CSV_PATH)
    errors = check_header(fields, FIELDS, "data/papers.csv")
    if errors:
        return errors
    errors += validate(rows)
    qfields, queue = load_table(QUEUE_PATH)
    if QUEUE_PATH.exists():
        errors += check_header(qfields, QUEUE_FIELDS, "data/review_queue.csv")
        if not errors:
            errors += validate_queue(queue, rows)
    return errors


# ------------------------------------------------------------------------ helpers
def cell(text: str) -> str:
    """Make text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def slugify(heading: str, used: Counter) -> str:
    """Reproduce GitHub's heading-anchor algorithm."""
    slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
    n = used[slug]
    used[slug] += 1
    return slug if n == 0 else f"{slug}-{n}"


def code_cell(r: dict) -> str:
    link = r.get("code_link", "")
    if not link:
        if r.get("code_status") == "Project page only" and r.get("project_link"):
            return f"[Project]({r['project_link']})"
        return "—"
    mark = "<sup>*</sup>" if r.get("code_status") == FOLLOW_UP else ""
    m = GITHUB_RE.match(link)
    if m:
        owner, repo = m.group(1), m.group(2).removesuffix(".git")
        badge = f"https://img.shields.io/github/stars/{owner}/{repo}?style=flat-square&logo=github&label=&color=24292f"
        return f"[![GitHub stars]({badge})]({link}){mark}"
    return f"[Code]({link}){mark}"


def venue_cell(r: dict) -> str:
    venue = r.get("venue_short") or r.get("venue") or "—"
    year = r.get("year", "")
    if year and year not in venue:
        return f"{cell(venue)}<br><sub>{year}</sub>"
    return cell(venue)


def model_cell(r: dict) -> str:
    name = cell(r["model_name"])
    if len(name) <= 18:  # keep short names on one line (non-breaking space and hyphen)
        name = name.replace(" ", "&nbsp;").replace("-", "‑")
    dagger = "&nbsp;‡" if r.get("context_level") == "Yes" else ""
    return f"**{name}**{dagger}"


def paper_row(r: dict) -> str:
    paper = f"[{cell(r['paper_name'])}]({r['paper_link']})"
    details = []
    if r.get("modality"):
        details.append(f"<code>{html.escape(cell(r['modality']))}</code>")
    if r.get("task"):
        details.append(cell(r["task"]))
    if r.get("survey_ref"):
        details.append(f"· ref.&nbsp;{r['survey_ref']}")
    if details:
        paper += f"<br><sub>{' '.join(details)}</sub>"
    return f"| {model_cell(r)} | {paper} | {venue_cell(r)} | {code_cell(r)} |"


TABLE_HEAD = "| Model | Paper | Venue | Code |\n| :-- | :-- | :-: | :-: |"
BACK_TO_TOP = '<p align="right"><a href="#contents"><sub>↑ back to top</sub></a></p>'
BAR_WIDTH = 24  # characters for the largest bar in the year chart


def sort_key(r: dict):
    """Taxonomy order first, then newest first, then model name."""
    return (load_taxonomy().order_key(r[CLASS_COL], r[SUB_COL]), -int(r["year"]), r["model_name"].lower())


# ------------------------------------------------------------------------- render
def grouped(rows: list[dict]) -> list[tuple[object, list[tuple[str, list[dict]]]]]:
    """[(class, [(subcategory, rows), ...]), ...] in canonical order. Every class is returned
    (possibly empty); only subcategories with papers are. A row outside the taxonomy raises,
    so an unknown value can never become a heading."""
    tax = load_taxonomy()
    for r in rows:
        problem = tax.check(r.get(CLASS_COL, ""), r.get(SUB_COL, ""))
        if problem:
            raise ValueError(f"{r.get('model_name')}: {problem}")
    out = []
    for c in tax.classes:
        subs = []
        for s in c.subcategories:
            items = sorted((r for r in rows if r[CLASS_COL] == c.name and r[SUB_COL] == s), key=sort_key)
            if items:
                subs.append((s, items))
        out.append((c, subs))
    return out


def class_heading(c) -> str:
    return f"{c.icon} {c.letter}. {c.name}".strip()


def counts(rows: list[dict]) -> tuple[int, int]:
    """(primary method/application records, surveys excluded from that count)."""
    tax = load_taxonomy()
    eligible = sum(1 for r in rows if tax.is_eligible(r[CLASS_COL]))
    return eligible, len(rows) - eligible


def render_years(rows: list[dict]) -> str:
    years = sorted(Counter(r["year"] for r in rows).items())
    peak = max(n for _, n in years)
    lines = ["| Year | Papers | |", "| :-- | --: | :-- |"]
    for year, n in years:
        bar = "█" * max(1, round(n / peak * BAR_WIDTH))
        lines.append(f"| {year} | {n} | {bar} |")
    return "\n".join(lines)


def template_headings(text: str) -> list[str]:
    """Markdown headings in a template, skipping fenced code blocks."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and (m := re.match(r"#{1,6} (.+)", line)):
            out.append(m.group(1).strip())
    return out


def render(rows: list[dict], queued: int = 0) -> str:
    tax = load_taxonomy()
    header = (TEMPLATES / "header.md").read_text(encoding="utf-8")
    footer = (TEMPLATES / "footer.md").read_text(encoding="utf-8")

    used: Counter = Counter()
    # Reserve anchors for headings that appear in the header before the sections.
    for h in template_headings(header):
        slugify(h, used)

    toc = ["| | Loop family | Papers | Primary | Branches |", "| :-: | :-- | :-: | :-: | :-- |"]
    body = []
    for c, subs in grouped(rows):
        anchor = slugify(class_heading(c), used)
        n = sum(len(items) for _, items in subs)
        body.append(f"## {class_heading(c)}\n")
        body.append(f"> {c.definition}\n")
        links = []
        if not subs:
            body.append("_No papers in this class yet._\n")
        for s, items in subs:
            sub_anchor = slugify(s, used)
            links.append(f"[{s}](#{sub_anchor})&nbsp;<sub>{len(items)}</sub>")
            body.append(f"### {s}\n")
            body.append(TABLE_HEAD)
            body.extend(paper_row(r) for r in items)
            body.append(f"\n{BACK_TO_TOP}\n")
        toc.append(f"| {c.icon} | **[{c.letter}. {c.name}](#{anchor})** | {n} | {'Yes' if c.eligible else 'No'} | "
                   f"{' · '.join(links) or '—'} |")

    classes = ["| Loop family | What is iterated | Timescale | Typical risk |", "| --- | --- | :-: | --- |"]
    classes += [f"| {c.icon} **{c.letter}. {c.name}** | {cell(c.state) or '—'} | {cell(c.timescale) or '—'} | "
                f"{cell(c.risk) or '—'} |" for c in tax.classes if c.eligible]
    eligible, adjacent = counts(rows)
    with_code = sum(1 for r in rows if r.get("code_link"))
    context = sum(1 for r in rows if r.get("context_level") == "Yes")
    header = (
        header.replace("{{TOTAL}}", str(len(rows)))
        .replace("{{WITH_CODE}}", str(with_code))
        .replace("{{PRIMARY}}", str(eligible))
        .replace("{{SURVEYS}}", str(adjacent))
        .replace("{{CONTEXT}}", str(context))
        .replace("{{QUEUED}}", str(queued))
        .replace("{{CLASS_COUNT}}", str(len(tax.classes)))
        .replace("{{CLASSES}}", "\n".join(classes))
        .replace("{{YEARS}}", render_years(rows))
        .replace("{{TOC}}", "\n".join(toc))
    )
    note = "<!-- This file is generated by scripts/build_readme.py from data/papers.csv and config/taxonomy.json. Do not edit it by hand. -->\n\n"
    return note + header.rstrip() + "\n\n" + "\n".join(body).rstrip() + "\n\n" + footer.rstrip() + "\n"


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if README.md is not up to date")
    args = ap.parse_args()

    errors = validate_all()
    if errors:
        print("Found problems in the data files:", *errors, sep="\n  - ", file=sys.stderr)
        return 1
    rows = load_rows()
    readme = render(rows, queued=len(load_table(QUEUE_PATH)[1]))
    if args.check:
        current = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
        if current != readme:
            print("README.md is out of date. Run: python scripts/build_readme.py", file=sys.stderr)
            return 1
        print(f"README.md is up to date ({len(rows)} papers).")
        return 0

    README_PATH.write_text(readme, encoding="utf-8")
    print(f"Wrote README.md with {len(rows)} papers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
