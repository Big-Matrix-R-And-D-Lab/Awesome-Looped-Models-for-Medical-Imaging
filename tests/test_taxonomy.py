"""Regression tests for the closed survey taxonomy. Standard library only:

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import contextlib
import csv
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_readme  # noqa: E402
import import_papers  # noqa: E402
from taxonomy import load  # noqa: E402

# The manuscript's Figure 3 (five loop families and their branches, in order) plus its survey class.
FIGURE_3 = [
    ("Recurrent, recursive & equilibrium", [
        "Recurrent conv. segmentation", "Recursive transformer U-Net", "Recurrent dynamic MRI recon.",
        "Recurrent mask refinement", "Deep equilibrium models"]),
    ("Unrolled & data-consistency reconstruction", [
        "Weight-shared unrolling", "Recurrent inference machines", "Recurrent variational network",
        "Multi-prior, edge, alignment DUNs", "Multi-contrast SR unfolding", "Motion search with data consistency"]),
    ("Test-time loops", [
        "Per-image weight / norm. adaptation", "Input, prompt, embedding TTA", "Test-time training",
        "Concept-level correction", "VLM reasoning, test-time scaling"]),
    ("Data-feedback training loops", [
        "Co-training, mutual learning", "Self-training, distillation", "Pseudo-label-guided synthesis",
        "Training-data refinement", "Active learning"]),
    ("Human, deployment & lifelong loops", [
        "Interactive / clinician correction", "HITL annotation engines", "Post-deployment drift correction",
        "Continual memory replay", "Self-improving agents, roadmap"]),
    ("Surveys", ["Background only"]),
]
# Manuscript counts: Fig. 3 (49 primary records) and the survey class (7).
MANUSCRIPT_COUNTS = {"Recurrent, recursive & equilibrium": 7, "Unrolled & data-consistency reconstruction": 9,
                     "Test-time loops": 13, "Data-feedback training loops": 11,
                     "Human, deployment & lifelong loops": 9, "Surveys": 7}


def row(**over) -> dict:
    r = {k: "" for k in build_readme.FIELDS}
    r.update(paper_name="A looped test paper", paper_link="https://arxiv.org/abs/2601.00001", year="2026",
             model_name="LoopNet", taxonomy_class="Test-time loops", taxonomy_subcategory="Test-time training",
             venue="arXiv preprint", venue_short="arXiv")
    r.update(over)
    return r


class TaxonomyTests(unittest.TestCase):
    def setUp(self):
        self.tax = load()

    def test_classes_and_branches_match_figure_3_exactly(self):
        self.assertEqual([(c.name, list(c.subcategories)) for c in self.tax.classes], FIGURE_3)

    def test_only_surveys_are_excluded_from_the_primary_count(self):
        self.assertEqual([c.name for c in self.tax.classes if not c.eligible], ["Surveys"])

    def test_every_approved_pair_is_accepted(self):
        for cls, sub in self.tax.combos():
            self.assertIsNone(self.tax.check(cls, sub), f"{cls} > {sub}")

    def test_unapproved_subcategory_is_rejected(self):
        self.assertIsNotNone(self.tax.check("Test-time loops", "Agents"))
        self.assertIsNotNone(self.tax.check("Recurrent, recursive & equilibrium", "Other"))

    def test_valid_branch_under_wrong_family_is_rejected(self):
        msg = self.tax.check("Test-time loops", "Active learning")
        self.assertIn("Data-feedback training loops", msg)

    def test_unknown_family_is_rejected(self):
        self.assertIsNotNone(self.tax.check("Hybrid loops", "Test-time training"))

    def test_table_s1_short_labels_normalise(self):
        self.assertEqual(self.tax.normalize_class("Unrolled/DC"), "Unrolled & data-consistency reconstruction")
        self.assertEqual(self.tax.normalize_class("deployment/human"), "Human, deployment & lifelong loops")

    def test_raw_primary_category_labels_do_not_normalise(self):
        # "iterative reconstruction" maps to two families in the manuscript, so it must never resolve.
        for raw in ("iterative reconstruction", "recurrent depth", "co-training", "cs.LG"):
            self.assertIsNone(self.tax.normalize_class(raw), raw)


class DataTests(unittest.TestCase):
    def test_published_data_validates(self):
        self.assertEqual(build_readme.validate_all(), [])

    def test_counts_match_the_manuscript(self):
        rows = build_readme.load_rows()
        counts = {c.name: sum(len(items) for _, items in subs) for c, subs in build_readme.grouped(rows)}
        self.assertEqual(counts, MANUSCRIPT_COUNTS)
        self.assertEqual(build_readme.counts(rows), (49, 7))

    def test_every_record_has_a_unique_survey_reference(self):
        refs = [r["survey_ref"] for r in build_readme.load_rows()]
        self.assertEqual(len(refs), len(set(refs)))

    def test_follow_up_links_are_not_marked_official(self):
        for r in build_readme.load_rows():
            if r["code_status"] == build_readme.FOLLOW_UP:
                self.assertEqual(r["official_code"], "No", r["model_name"])


class ReadmeTests(unittest.TestCase):
    def test_readme_has_exactly_the_approved_headings_in_order(self):
        text = build_readme.render(build_readme.load_rows())
        tax = load()
        h2 = re.findall(r"^## (.+)$", text, re.M)
        class_h2 = [h for h in h2 if re.match(r"^\S+ [1-5S]\. ", h)]
        self.assertEqual(class_h2, [build_readme.class_heading(c) for c in tax.classes])
        allowed = set(tax.all_subcategories())
        for h in re.findall(r"^### (.+)$", text, re.M):
            self.assertIn(h, allowed)

    def test_unknown_class_cannot_become_a_heading(self):
        with self.assertRaises(ValueError):
            build_readme.grouped([row(taxonomy_class="Other loops", taxonomy_subcategory="Misc")])
        errors = build_readme.validate([row(taxonomy_subcategory="Agents")])
        self.assertTrue(errors)


class ImportTests(unittest.TestCase):
    """The bulk and single-paper paths both run import_papers.py; run it against temporary files."""

    def run_import(self, incoming: list[dict], existing: list[dict] | None = None, extra=()):
        tmp = Path(tempfile.mkdtemp())
        papers, queue, src = tmp / "papers.csv", tmp / "review_queue.csv", tmp / "in.csv"
        for path, rows, fields in ((papers, existing or [], build_readme.FIELDS), (queue, [], build_readme.QUEUE_FIELDS)):
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
                w.writeheader()
                w.writerows(rows)
        fields = sorted({k for r in incoming for k in r})
        with src.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
            w.writeheader()
            w.writerows(incoming)
        old = (import_papers.CSV_PATH, import_papers.QUEUE_PATH, sys.argv)
        import_papers.CSV_PATH, import_papers.QUEUE_PATH = papers, queue
        sys.argv = ["import_papers.py", str(src), *extra]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = import_papers.main()
        finally:
            import_papers.CSV_PATH, import_papers.QUEUE_PATH, sys.argv = old
        def read(p: Path) -> list[dict]:
            with p.open(encoding="utf-8") as f:
                return list(csv.DictReader(f))
        return code, read(papers), read(queue)

    def test_valid_row_is_added(self):
        code, papers, queue = self.run_import([row()])
        self.assertEqual((code, len(papers), len(queue)), (0, 1, 0))

    def test_unknown_section_is_queued_not_created(self):
        code, papers, queue = self.run_import([row(taxonomy_class="", taxonomy_subcategory="",
                                                   section="Medical Imaging > Iterative Methods")])
        self.assertEqual((code, len(papers), len(queue)), (2, 0, 1))
        self.assertIn("is not one of", queue[0]["review_reason"])

    def test_raw_primary_category_alone_is_queued(self):
        code, papers, queue = self.run_import([row(taxonomy_class="", taxonomy_subcategory="",
                                                   primary_category="iterative reconstruction")])
        self.assertEqual((code, len(papers), len(queue)), (2, 0, 1))

    def test_branch_under_wrong_family_is_queued(self):
        code, papers, queue = self.run_import([row(taxonomy_subcategory="Active learning")])
        self.assertEqual((len(papers), len(queue)), (0, 1))

    def test_low_confidence_is_queued(self):
        code, papers, queue = self.run_import([row(classification_confidence="low")])
        self.assertEqual((len(papers), len(queue)), (0, 1))

    def test_alias_is_normalised(self):
        code, papers, _ = self.run_import([row(taxonomy_class="Test-time")])
        self.assertEqual(papers[0]["taxonomy_class"], "Test-time loops")

    def test_multimodal_row_keeps_modalities_without_new_section(self):
        code, papers, _ = self.run_import([row(modality="MRI; CT; histopathology")])
        self.assertEqual(papers[0]["modality"], "MRI; CT; histopathology")
        self.assertEqual(papers[0]["taxonomy_subcategory"], "Test-time training")

    def test_duplicate_is_skipped_and_existing_metadata_kept(self):
        existing = row(notes="keep me", code_status="No project-specific URL found")
        code, papers, queue = self.run_import([row(paper_name="A Looped Test Paper!")], existing=[existing])
        self.assertEqual((code, len(papers), len(queue)), (3, 1, 0))
        self.assertEqual(papers[0]["notes"], "keep me")

    def test_single_paper_path_does_not_write_the_queue(self):
        code, papers, queue = self.run_import([row(taxonomy_class="")], extra=["--no-queue"])
        self.assertEqual((len(papers), len(queue)), (0, 0))


if __name__ == "__main__":
    unittest.main()
