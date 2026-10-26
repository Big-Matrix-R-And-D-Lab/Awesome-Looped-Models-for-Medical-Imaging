#!/usr/bin/env python3
"""Merge a CSV of papers into data/papers.csv, enforcing the closed survey taxonomy.

Usage:
    python scripts/import_papers.py <incoming.csv> [--summary summary.md] [--skipped skipped.md]
                                    [--suggested-by LOGIN] [--no-queue]

Every ingestion route (bulk-import issues, "Add a paper" issues, local imports) goes through
this script, and every row is checked against config/taxonomy.json before anything is written.

Classification comes from `taxonomy_class` + `taxonomy_subcategory` (or a combined
`classification` / `section` value written as "Class > Subcategory"). Recognisable spelling
variants are normalised to the canonical names (config/taxonomy.json `aliases`); nothing else is
inferred, and a raw `primary_category` label is never used to pick a family. A row is sent to
data/review_queue.csv, with all its metadata and the reason, when:
  - it has no classification, or only a raw label (e.g. "iterative reconstruction", which the
    survey maps to two different families);
  - its class or subcategory is not in the taxonomy (e.g. "Test-time loops > Agents");
  - its subcategory is not approved under its class (e.g. "Test-time loops > Active learning");
  - `classification_confidence` is `low`.
Unknown values never create a section. With --no-queue (single-paper issues) such rows are
reported but not written, and the issue itself stays open for a maintainer.

Rows are skipped, with the reason, when they duplicate a paper already listed or queued (same
title, DOI or link) or repeated earlier in the CSV, or when their metadata is invalid.
Authors written as "First Last; ..." are converted to "Last, First; ...".

Exit codes: 0 = papers added (some may also be queued), 2 = papers only queued for review,
3 = nothing changed, 1 = the file itself is unusable. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

from build_readme import (
    CSV_PATH,
    FIELDS,
    QUEUE_FIELDS,
    QUEUE_PATH,
    check_metadata,
    title_key,
    validate,
    validate_queue,
)
from taxonomy import CLASS_COL, SUB_COL, load as load_taxonomy

MAX_ROWS = 500
REQUIRED_INCOMING = ["paper_name", "paper_link", "year", "model_name"]
COMBINED_COLS = ("classification", "section")  # "Class > Subcategory" in one cell


def resolve_classification(r: dict) -> tuple[str, str, str | None, list[str]]:
    """Return (class, subcategory, problem, notes).

    problem is None only when the row carries an approved, unambiguous classification.
    Values are normalised through the taxonomy aliases; nothing is guessed from keywords.
    """
    tax = load_taxonomy()
    notes: list[str] = []
    raw_cls, raw_sub = r.get(CLASS_COL, "").strip(), r.get(SUB_COL, "").strip()
    combined = next((r.get(c, "").strip() for c in COMBINED_COLS if r.get(c, "").strip()), "")
    if not raw_cls and not raw_sub and combined:
        if ">" not in combined:
            return "", "", f"'{combined}' is not written as 'Class > Subcategory' from the survey taxonomy", notes
        left, _, right = combined.partition(">")
        raw_cls, raw_sub = left.strip(), right.strip()
    if not raw_cls and not raw_sub:
        return "", "", "no survey classification given", notes

    cls, sub = tax.normalize_class(raw_cls), tax.normalize_subcategory(raw_sub)
    if raw_cls and cls is None:
        return "", "", f"class '{raw_cls}' is not one of {tax.class_names} (or is ambiguous)", notes
    if raw_sub and sub is None:
        return "", "", f"subcategory '{raw_sub}' is not in the survey taxonomy", notes
    if not cls:
        return "", "", "missing taxonomy_class", notes
    if not sub:
        return "", "", "missing taxonomy_subcategory", notes
    if not tax.is_valid(cls, sub):
        allowed = [c.name for c in tax.classes if sub in c.subcategories]
        return "", "", f"'{sub}' is not an approved subcategory of '{cls}' (approved under {allowed} only)", notes
    if cls != raw_cls:
        notes.append(f"class '{raw_cls}' normalised to '{cls}'")
    if sub != raw_sub:
        notes.append(f"subcategory '{raw_sub}' normalised to '{sub}'")
    if r.get("classification_confidence", "").strip().lower() == "low":
        return cls, sub, "classification confidence is low", notes
    return cls, sub, None, notes


def suggestion(r: dict) -> str:
    """Keyword hint for the reviewer. Shown only; never applied."""
    text = " ".join(r.get(k, "") for k in ("modality", "task", "loop_mechanism", "paper_name",
                                            "source_primary_category", "primary_category"))
    hits = load_taxonomy().suggest_subcategories(text)
    return f" Keyword hint (not applied): {', '.join(hits[:3])}." if hits else ""


KNOWN_VENUES = [
    "MICCAI", "MIDL", "ML4H", "CHIL", "ICML", "ICLR", "NeurIPS", "CVPR", "ICCV", "ECCV", "WACV", "KDD",
    "AAAI", "IJCAI", "EMNLP", "ACL", "NAACL", "ISBI", "IPMI", "ACIIDS", "TMLR", "MLHC", "BIBM", "EMBC",
]
NAME_PARTICLES = {"van", "von", "de", "der", "den", "del", "della", "da", "di", "du", "la", "le", "el", "al",
                  "bin", "dos", "das", "ter", "ten"}


def infer_venue_short(venue: str) -> str:
    v = venue.lower()
    for name in ("arXiv", "medRxiv", "bioRxiv"):
        if name.lower() in v:
            return name
    for name in KNOWN_VENUES:
        if re.search(rf"\b{re.escape(name)}\b", venue, re.IGNORECASE):
            return f"{name} Workshop" if "workshop" in v else name
    head = re.split(r"[,(;]", venue)[0]
    head = re.sub(r"\b(19|20)\d\d\b", "", head).strip()
    return head[:40] or venue[:40]


def last_first(name: str) -> tuple[str, bool]:
    """'First Middle Last' -> 'Last, First Middle'. Returns (name, uncertain)."""
    name = " ".join(name.split())
    if "," in name or " " not in name:
        return name, False
    parts = name.split(" ")
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in NAME_PARTICLES:
        i -= 1
    family, given = " ".join(parts[i:]), " ".join(parts[:i])
    return f"{family}, {given}", len(parts) >= 3 and i == len(parts) - 1


def convert_authors(authors: str) -> tuple[str, list[str]]:
    if not authors or ";" not in authors and "," in authors:
        return authors, []  # empty, or already "Last, First"
    out, unsure = [], []
    for a in authors.split(";"):
        if not a.strip():
            continue
        converted, uncertain = last_first(a)
        out.append(converted)
        if uncertain:
            unsure.append(a.strip())
    return "; ".join(out), unsure


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    text = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]
    return [f.strip() for f in reader.fieldnames or []], rows


def write_csv(path, fields: list[str], rows: list[dict], eol: str = "\n") -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator=eol, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buf.getvalue(), encoding="utf-8", newline="")


def read_existing(path: Path, expected: list[str]) -> tuple[str, list[dict]]:
    if not path.exists():
        return "\n", []
    raw = path.read_text(encoding="utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    fields = [f.strip() for f in reader.fieldnames or []]
    if fields != expected:
        raise SystemExit(f"{path.name} does not have the canonical columns; run build_readme.py to see why")
    return ("\r\n" if "\r\n" in raw else "\n"), list(reader)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("incoming", type=Path)
    ap.add_argument("--summary", type=Path, help="write a Markdown review summary here")
    ap.add_argument("--suggested-by", default="", help="GitHub username to credit in `suggested_by` when empty")
    ap.add_argument("--skipped", type=Path, help="write the 'Not added' table (papers skipped, with reasons) here")
    ap.add_argument("--no-queue", action="store_true",
                    help="report rows that need review but do not write them to data/review_queue.csv")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # titles and the summary are not ASCII-only

    lines: list[str] = []

    def finish(code: int) -> int:
        if args.summary:
            args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print("\n".join(lines))
        return code

    try:
        in_fields, incoming = read_csv(args.incoming)
    except (UnicodeDecodeError, csv.Error) as exc:
        lines.append(f"**Could not read the CSV:** {exc}")
        return finish(1)
    missing = [c for c in REQUIRED_INCOMING if c not in in_fields]
    if missing:
        lines.append(f"**The CSV is missing required columns:** {', '.join(f'`{c}`' for c in missing)}")
        return finish(1)
    incoming = [r for r in incoming if any(r.values())]
    if len(incoming) > MAX_ROWS:
        lines.append(f"**Too many rows:** {len(incoming)} (limit {MAX_ROWS}). Split the file and try again.")
        return finish(1)

    eol, existing = read_existing(CSV_PATH, FIELDS)
    qeol, queue = read_existing(QUEUE_PATH, QUEUE_FIELDS)
    # key -> label of the entry it belongs to, so a skip can say what it matched
    seen_titles, seen_dois, seen_links = {}, {}, {}
    for where, rows in (("already in the list", existing), ("already in the review queue", queue)):
        for r in rows:
            seen_titles[title_key(r["paper_name"])] = (r["model_name"], where)
            if r.get("doi"):
                seen_dois[r["doi"].lower()] = (r["model_name"], where)
            seen_links[r["paper_link"].rstrip("/")] = (r["model_name"], where)

    known = set(FIELDS) | set(COMBINED_COLS)
    unknown = [c for c in in_fields if c and c not in known]
    added, queued, skipped = [], [], []  # skipped: (title, reason)

    def remember(row: dict) -> None:
        seen_titles[title_key(row["paper_name"])] = (row["model_name"], "earlier in this CSV")
        if row.get("doi"):
            seen_dois[row["doi"].lower()] = (row["model_name"], "earlier in this CSV")
        seen_links[row["paper_link"].rstrip("/")] = (row["model_name"], "earlier in this CSV")

    for r in incoming:
        title = r.get("paper_name", "") or "(no title)"
        doi, link = r.get("doi", "").lower(), r.get("paper_link", "").rstrip("/")
        match = (("title", seen_titles.get(title_key(title))) if title_key(title) in seen_titles else
                 ("DOI", seen_dois.get(doi)) if doi and doi in seen_dois else
                 ("paper link", seen_links.get(link)) if link and link in seen_links else None)
        if match:
            skipped.append((title, f"Duplicate: same {match[0]} as **{match[1][0]}**, {match[1][1]}"))
            continue

        row = {k: r.get(k, "") for k in FIELDS}
        if not row["suggested_by"] and args.suggested_by:
            row["suggested_by"] = args.suggested_by
        notes = []
        if not row["publication_status"] and row["venue_short"].lower() == "arxiv":
            row["publication_status"] = "Preprint"
        if not row["venue_short"] and row["venue"]:
            row["venue_short"] = infer_venue_short(row["venue"])
            notes.append("short venue guessed")
        oc = row.get("official_code", "")
        if oc and oc not in ("Yes", "No"):
            # Team sheets often write e.g. "Yes – paper-linked repository" or "No verified code".
            m = re.match(r"(yes|no)\b[\s\W]*(.*)", oc, re.IGNORECASE)
            if m:
                row["official_code"] = m.group(1).capitalize()
                detail = m.group(2).replace("\ufffd", "-").strip()
                if detail:
                    row["code_status"] = f"{row['code_status']}; {detail}" if row.get("code_status") else detail
                notes.append(f"official_code \"{oc[:30]}\" read as {row['official_code']}")
        if row["code_link"] and not row["code_status"]:
            row["code_status"] = "Code link supplied in the issue"
            notes.append("code_status set to 'Code link supplied in the issue': confirm the repository")
        if not row["code_link"] and not row["code_status"]:
            row["code_status"] = "No project-specific URL found"
        if row["official_code"] == "Yes" and row["code_status"] not in (
                "Linked from the official paper page", "Curated record", "Code link supplied in the issue"):
            row["official_code"] = "No"
            notes.append("official_code set to No: code_status does not show an author-released link")
        row["classification_confidence"] = row["classification_confidence"].strip().lower()
        row["authors"], unsure = convert_authors(row["authors"])
        if unsure:
            notes.append("check family names: " + ", ".join(unsure[:4]) + (" …" if len(unsure) > 4 else ""))

        # Metadata first: a row that cannot be stored anywhere is reported, not queued.
        problems = [e.removeprefix("row: ") for e in check_metadata(row, "row")]
        if problems:
            skipped.append((title, "Invalid: " + "; ".join(problems)))
            continue

        cls, sub, problem, tax_notes = resolve_classification(r)
        notes += tax_notes
        if problem:
            row[CLASS_COL], row[SUB_COL] = cls, sub  # a valid pair is kept as a suggestion only
            provided = ", ".join(f"{c}='{r[c]}'" for c in (CLASS_COL, SUB_COL, *COMBINED_COLS, "primary_category")
                                 if r.get(c, "").strip())
            reason = f"Needs review: {problem}." + (f" Provided: {provided}." if provided else "") + suggestion(r)
            queued.append({**row, "review_reason": reason})
            remember(row)
            continue
        row[CLASS_COL], row[SUB_COL] = cls, sub
        # Defence in depth: the exact rules used for the published list.
        problems = [re.sub(r"^\S+ line \d+: ", "", e) for e in validate([row])]
        if problems:
            skipped.append((title, "Invalid: " + "; ".join(problems)))
            continue
        added.append((row, notes))
        remember(row)

    new_existing = existing + [row for row, _ in added]
    new_queue = queue + ([] if args.no_queue else queued)
    errors = validate(new_existing) + validate_queue(new_queue, new_existing)
    if errors:
        lines.append("**The merged data did not pass validation, so nothing was changed:**")
        lines.extend(f"- {e}" for e in errors[:50])
        return finish(1)

    cell = lambda s: s.replace("|", "\\|").replace("\n", " ")
    not_added = []
    if skipped:
        not_added = [f"**Not added ({len(skipped)} of {len(incoming)}):**", "", "| Paper | Reason |", "| --- | --- |"]
        not_added += [f"| {cell(t)} | {cell(reason)} |" for t, reason in skipped[:300]]
    review = []
    if queued:
        where = ("Not written (single-paper submission): a maintainer must classify it in the issue."
                 if args.no_queue else "Added to `data/review_queue.csv`, not to the published list.")
        review = [f"**Needs maintainer classification ({len(queued)} of {len(incoming)}).** {where}", "",
                  "| Paper | Reason |", "| --- | --- |"]
        review += [f"| {cell(q['paper_name'])} | {cell(q['review_reason'])} |" for q in queued[:300]]
    if args.skipped:
        args.skipped.write_text("\n".join(not_added + ([""] if not_added and review else []) + review)
                                + ("\n" if not_added or review else ""), encoding="utf-8")

    if added:
        write_csv(CSV_PATH, FIELDS, new_existing, eol)
    if queued and not args.no_queue:
        write_csv(QUEUE_PATH, QUEUE_FIELDS, new_queue, qeol)

    if not added:
        lines.append(f"No papers were added to the published list from this CSV ({len(incoming)} rows).")
        if queued and not args.no_queue:
            lines.append(f"Queues **{len(queued)}** for maintainer classification.")
        for block in (review, not_added):
            if block:
                lines += [""] + block
        return finish(2 if queued and not args.no_queue else 3)

    lines.append(f"Adds **{len(added)}** of {len(incoming)} papers in the CSV ({len(new_existing)} in the list now).")
    if queued and not args.no_queue:
        lines.append(f"Queues **{len(queued)}** for maintainer classification.")
    if unknown:
        lines.append(f"Ignored unknown columns: {', '.join(f'`{c}`' for c in unknown)}")
    lines += ["", "| Model | Year | Classification | Venue | Check |", "| --- | --- | --- | --- | --- |"]
    tax = load_taxonomy()
    for row, notes in added:
        check = "; ".join(notes) if notes else "—"
        lines.append(f"| {cell(row['model_name'])} | {row['year']} | {cell(tax.label(row[CLASS_COL], row[SUB_COL]))} | "
                     f"{cell(row['venue_short'])} | {cell(check)} |")
    lines += ["", "Every classification above was validated against `config/taxonomy.json`. Rows marked in **Check** "
              "had values filled in or normalised automatically; edit `data/papers.csv` on this branch if needed."]
    for block in (review, not_added):
        if block:
            lines += [""] + block
    return finish(0)


if __name__ == "__main__":
    sys.exit(main())
