#!/usr/bin/env python3
"""The survey taxonomy: load, validate, normalise, and render the files generated from it.

config/taxonomy.json is the single source of truth. Every other component (CSV validation,
README and website grouping, the bulk and single-paper import paths, the "Add a paper"
issue form and Claude's classification guide) reads it through this module. Nothing here
can add a class or subcategory: values outside the config are rejected, never appended.

Usage:
    python scripts/taxonomy.py            # print the taxonomy
    python scripts/taxonomy.py --write    # regenerate the files derived from the taxonomy
    python scripts/taxonomy.py --check    # fail if a derived file is out of date (used in CI)

Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "taxonomy.json"
ISSUE_FORM_PATH = ROOT / ".github" / "ISSUE_TEMPLATE" / "add-paper.yml"
GUIDE_PATH = ROOT / "docs" / "classification-guide.md"

CLASS_COL = "taxonomy_class"
SUB_COL = "taxonomy_subcategory"
NOT_SURE = "Not sure: let a maintainer classify it"


class TaxonomyError(ValueError):
    """The taxonomy config itself is malformed."""


@dataclass(frozen=True)
class TaxClass:
    id: str
    letter: str
    name: str
    icon: str
    eligible: bool
    definition: str
    subcategories: tuple[str, ...]
    short: str = ""
    state: str = ""
    timescale: str = ""
    risk: str = ""


@dataclass(frozen=True)
class Taxonomy:
    version: int
    separator: str
    classes: tuple[TaxClass, ...]
    class_aliases: dict
    sub_aliases: dict
    hints: dict

    # ---------------------------------------------------------------- lookups
    @property
    def class_names(self) -> list[str]:
        return [c.name for c in self.classes]

    def get(self, name: str) -> TaxClass | None:
        return next((c for c in self.classes if c.name == name), None)

    def all_subcategories(self) -> set[str]:
        return {s for c in self.classes for s in c.subcategories}

    def combos(self) -> list[tuple[str, str]]:
        """Every approved (class, subcategory) pair, in canonical display order."""
        return [(c.name, s) for c in self.classes for s in c.subcategories]

    def label(self, cls: str, sub: str) -> str:
        return f"{cls}{self.separator}{sub}"

    def is_valid(self, cls: str, sub: str) -> bool:
        c = self.get(cls)
        return c is not None and sub in c.subcategories

    def is_eligible(self, cls: str) -> bool:
        c = self.get(cls)
        return bool(c and c.eligible)

    def order_key(self, cls: str, sub: str) -> tuple[int, int]:
        c = self.get(cls)
        if c is None or sub not in c.subcategories:
            raise KeyError(f"'{self.label(cls, sub)}' is not in the survey taxonomy")
        return self.classes.index(c), c.subcategories.index(sub)

    # ---------------------------------------------------------- normalisation
    def normalize_class(self, value: str) -> str | None:
        """Canonical class name for an exact or alias spelling, else None (never guesses)."""
        key = _key(value)
        if not key:
            return None
        for name in self.class_names:
            if _key(name) == key:
                return name
        return self.class_aliases.get(key)

    def normalize_subcategory(self, value: str) -> str | None:
        key = _key(value)
        if not key:
            return None
        for name in self.all_subcategories():
            if _key(name) == key:
                return name
        return self.sub_aliases.get(key)

    def parse_label(self, value: str) -> tuple[str | None, str | None]:
        """Split 'Class > Subcategory' (canonical or alias spellings) into canonical parts."""
        if not value or ">" not in value:
            return None, None
        left, _, right = value.partition(">")
        return self.normalize_class(left), self.normalize_subcategory(right)

    def check(self, cls: str, sub: str) -> str | None:
        """None if (cls, sub) is an approved, canonically spelled pair; else the reason."""
        if not cls and not sub:
            return "no survey classification"
        if not cls:
            return "missing taxonomy_class"
        if not sub:
            return "missing taxonomy_subcategory"
        c = self.get(cls)
        if c is None:
            canon = self.normalize_class(cls)
            hint = f" (did you mean '{canon}'?)" if canon else ""
            return f"taxonomy_class '{cls}' is not one of {self.class_names}{hint}"
        if sub not in c.subcategories:
            canon = self.normalize_subcategory(sub)
            if canon and canon in c.subcategories:
                return f"taxonomy_subcategory '{sub}' must be written exactly as '{canon}'"
            others = [k.name for k in self.classes if (canon or sub) in k.subcategories]
            where = f"; it exists only under {others}" if others else "; it is not in the survey taxonomy"
            return f"'{sub}' is not an approved subcategory of '{cls}'{where}"
        return None

    def suggest_subcategories(self, text: str) -> list[str]:
        """Keyword hints for reviewers only. Never applied automatically."""
        t = " " + " ".join(text.lower().split())
        return [s for s, words in self.hints.items() if any(w in t for w in words)]


def _key(value: str) -> str:
    return " ".join((value or "").split()).casefold()


# --------------------------------------------------------------------------- loading
def _load(data: dict) -> Taxonomy:
    sep = data.get("separator", " > ")
    classes, seen = [], set()
    for raw in data.get("classes", []):
        name = raw.get("name", "").strip()
        subs = tuple(s.strip() for s in raw.get("subcategories", []))
        if not name or not subs:
            raise TaxonomyError(f"class {raw!r} needs a name and at least one subcategory")
        if _key(name) in seen:
            raise TaxonomyError(f"duplicate class '{name}'")
        seen.add(_key(name))
        if len({_key(s) for s in subs}) != len(subs):
            raise TaxonomyError(f"duplicate subcategory under '{name}'")
        if any(">" in s for s in (name, *subs)):
            raise TaxonomyError("names must not contain '>'")
        classes.append(TaxClass(raw.get("id", ""), raw.get("letter", ""), name, raw.get("icon", ""),
                                bool(raw.get("eligible")), raw.get("definition", ""), subs,
                                raw.get("short", "") or name, raw.get("state", ""),
                                raw.get("timescale", ""), raw.get("risk", "")))
    if not classes:
        raise TaxonomyError("no classes defined")
    names = {c.name for c in classes}
    subs_all = {s for c in classes for s in c.subcategories}
    aliases = data.get("aliases", {})
    class_aliases = {_key(k): v for k, v in aliases.get("classes", {}).items() if not k.startswith("$")}
    sub_aliases = {_key(k): v for k, v in aliases.get("subcategories", {}).items() if not k.startswith("$")}
    for k, v in class_aliases.items():
        if v not in names:
            raise TaxonomyError(f"class alias '{k}' points to unknown class '{v}'")
    for k, v in sub_aliases.items():
        if v not in subs_all:
            raise TaxonomyError(f"subcategory alias '{k}' points to unknown subcategory '{v}'")
    hints = {k: [w.lower() for w in v] for k, v in data.get("hints", {}).items() if not k.startswith("$")}
    for k in hints:
        if k not in subs_all:
            raise TaxonomyError(f"hint key '{k}' is not an approved subcategory")
    return Taxonomy(int(data.get("version", 1)), sep, tuple(classes), class_aliases, sub_aliases, hints)


@lru_cache(maxsize=1)
def load(path: Path = CONFIG_PATH) -> Taxonomy:
    return _load(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------------------------------------------------------------- derived files
def render_issue_form(tax: Taxonomy) -> str:
    options = "\n".join(f"        - \"{tax.label(c, s)}\"" for c, s in tax.combos())
    families = ", ".join(f"{c.letter} {c.short}" for c in tax.classes)
    return f"""# GENERATED by scripts/taxonomy.py from config/taxonomy.json. Do not edit by hand:
# run `python scripts/taxonomy.py --write` after an approved taxonomy change.
name: Add a paper
description: Suggest a looped / iterative model for medical imaging for the list
title: "[Paper] "
labels: ["new paper"]
body:
  - type: markdown
    attributes:
      value: |
        Papers are grouped by the closed taxonomy of the survey *Looped Models for Medical Imaging*
        (its Figure 3: five loop families plus a survey class). Pick the one classification that fits
        the paper's central loop, or choose **Not sure** and a maintainer will classify it.
        New sections cannot be created from an issue. See the
        [classification guide](../blob/main/docs/classification-guide.md).
  - type: input
    id: title
    attributes:
      label: Paper title
    validations:
      required: true
  - type: input
    id: paper_link
    attributes:
      label: Paper link
      description: Publisher page, DOI or arXiv URL
    validations:
      required: true
  - type: input
    id: code_link
    attributes:
      label: Code link (if any)
      description: The repository released by the paper's authors (say in the notes if it is not linked from the paper)
  - type: input
    id: venue
    attributes:
      label: Venue and year
      placeholder: e.g. MICCAI 2026, or arXiv preprint 2026
  - type: input
    id: modality
    attributes:
      label: Imaging modality
      description: Descriptive only. List every modality the paper uses; this never creates a section.
      placeholder: e.g. MRI, CT, histopathology, fundus
  - type: input
    id: loop
    attributes:
      label: What is iterated?
      description: The loop in one line, stating the iterated state, the feedback and the stopping rule.
      placeholder: e.g. a shared CNN prior alternates with a conjugate-gradient data-consistency step for K = 10 stages
  - type: dropdown
    id: classification
    attributes:
      label: Survey classification
      description: Loop family and branch from the survey's Figure 3 ({families}).
      options:
        - "{NOT_SURE}"
{options}
    validations:
      required: true
  - type: textarea
    id: notes
    attributes:
      label: Anything else?
      description: Task, datasets, or the evidence for the classification
"""


def render_guide(tax: Taxonomy) -> str:
    rows = []
    for c in tax.classes:
        rows.append(f"| **{c.letter}. {c.name}** | {'Yes' if c.eligible else 'No (background only)'} | "
                    + ", ".join(f"`{s}`" for s in c.subcategories) + " |")
    defs = "\n".join(f"- **{c.letter}. {c.name}**: {c.definition}"
                     + (f" *Iterated state:* {c.state}; *timescale:* {c.timescale}; *typical risk:* {c.risk}." if c.state else "")
                     for c in tax.classes)
    combos = "\n".join(f"- `{tax.label(c, s)}`" for c, s in tax.combos())
    aliases = ", ".join(f"`{c.short}`" for c in tax.classes if c.short != c.name)
    return f"""<!-- GENERATED by scripts/taxonomy.py from config/taxonomy.json. Do not edit by hand. -->

# Classification guide (for maintainers and Claude)

Every paper in this repository is classified with the **closed taxonomy of the survey
*Looped Models for Medical Imaging***, defined in [`config/taxonomy.json`](../config/taxonomy.json).
The five loop families and their branches are the manuscript's Figure 3; the survey class is its
"Surveys (background only)" class. This guide is generated from that file.

## The taxonomy is closed

There are exactly {len(tax.classes)} top-level classes, in this order, each with a fixed list of subcategories:

| Class | Counts as a primary record | Approved subcategories (in display order) |
| --- | :-: | --- |
{chr(10).join(rows)}

**Never** invent, rename, merge or add a class or subcategory, including headings such as
"Other loops", "Hybrid loops", "Reconstruction", "Segmentation", "Agents" or "Miscellaneous".
A raw `primary_category` label in an uploaded CSV (for example `recurrent depth` or
`iterative reconstruction`) is not a reason to create one. Changing the taxonomy requires a
maintainer-approved PR to `config/taxonomy.json` plus its tests.

## Class definitions

{defs}

## Rules

1. Classify by **what is iterated**: the state (features, an image estimate, parameters or a prompt, the
   training set, a deployed model), the feedback that closes the loop, and the timescale of one iteration
   (manuscript Eq. (1) and Fig. 2). The task (reconstruction, segmentation) does not decide the family.
2. The manuscript's own placements are binding examples: weight-shared MoDL is unrolled, not recurrent;
   deep-equilibrium MRI reconstruction is recurrent/equilibrium even though the task is reconstruction;
   *Iterative Data Refinement* is data-feedback because its loop refines the training data, not the image;
   active learning is data-feedback, whereas annotation engines with interactive correction are human loops.
3. Do not classify a paper because its title says "iterative", "recurrent", "loop" or "self-". An ordinary
   training epoch or a feed-forward cascade with independent stages is not a loop.
4. If the classification is ambiguous, your confidence is low, or no approved branch fits, do **not** force it:
   leave `taxonomy_class` and `taxonomy_subcategory` empty, set `classification_confidence` to `low`, and
   explain in `notes`. The importer sends such rows to
   [`data/review_queue.csv`](../data/review_queue.csv) for a maintainer decision.
5. Surveys are listed but always excluded from the primary-record count. A paper that is a primary record
   but only context-level evidence keeps its family and gets `context_level` = `Yes` (shown as ‡).

## Output format for a bulk CSV

Use the columns of `data/papers.csv`. The classification columns are:

| Column | Value |
| --- | --- |
| `taxonomy_class` | One of: {", ".join(f"`{n}`" for n in tax.class_names)} (or empty when unsure) |
| `taxonomy_subcategory` | An approved subcategory **of that class** (or empty when unsure) |
| `classification_confidence` | Optional: `high`, `medium` or `low`. `low` always goes to review. |

Write the canonical spellings exactly. The short family labels of Supplementary Table S1 ({aliases})
are normalised, but anything outside the taxonomy is flagged, never accepted.

## Every approved classification

{combos}
"""


DERIVED = {ISSUE_FORM_PATH: render_issue_form, GUIDE_PATH: render_guide}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="regenerate derived files")
    g.add_argument("--check", action="store_true", help="fail if derived files are stale")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        tax = load()
    except (TaxonomyError, json.JSONDecodeError) as exc:
        print(f"config/taxonomy.json is invalid: {exc}", file=sys.stderr)
        return 1
    if not (args.write or args.check):
        for c in tax.classes:
            print(f"{c.letter}. {c.name}{'' if c.eligible else '  (excluded from eligible count)'}")
            for s in c.subcategories:
                print(f"    {s}")
        return 0
    stale = []
    for path, render in DERIVED.items():
        text = render(tax)
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != text:
            if args.write:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
                print(f"wrote {path.relative_to(ROOT)}")
            else:
                stale.append(str(path.relative_to(ROOT)))
    if stale:
        print("Out of date (run `python scripts/taxonomy.py --write`): " + ", ".join(stale), file=sys.stderr)
        return 1
    if args.check:
        print("Taxonomy-derived files are up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
