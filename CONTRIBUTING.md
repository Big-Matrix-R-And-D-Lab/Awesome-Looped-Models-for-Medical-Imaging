# Contributing to Awesome Looped Models for Medical Imaging

Thanks for helping keep this list complete and accurate.

## How the list works

`README.md` and the website are **generated**. The single source of truth is [`data/papers.csv`](data/papers.csv); `scripts/build_readme.py` turns it into the README and `scripts/build_site.py` into the website. Please do not edit the README by hand, because the next build will overwrite your change.

To change the intro text, legend or footer, edit `scripts/templates/header.md` or `scripts/templates/footer.md`.

## Adding a paper

**Option A: open an issue.** Use the [Add a paper](../../issues/new?template=add-paper.yml) template. Once a maintainer accepts it, a bot opens a pull request that adds the paper with **you as the commit author**, so you appear in the repository's contributors and on the paper's entry on the website.

**Option B: open a pull request.**

1. Add one row to `data/papers.csv` (columns are described below).
2. Run `python scripts/build_readme.py` (Python 3.9+, no packages needed). The script validates the CSV and stops with a clear message if something is wrong.
3. Commit both `data/papers.csv` and the regenerated `README.md`, then open the PR.

A GitHub Action re-runs the check on every PR and fails if the README is out of date.

**Option C (maintainers): bulk import.** Open a *Team: bulk import papers* issue with a CSV in the same columns. A bot validates every row against the taxonomy, adds the papers, rebuilds the README and opens a pull request; rows it cannot place go to [`data/review_queue.csv`](data/review_queue.csv) with the reason.

## Inclusion criteria

A paper belongs here if it has an **explicit loop** (a state that is updated repeatedly by an operator, using feedback, until a stopping rule) and a **medical imaging** application. The loop can sit inside the network, in a reconstruction solver, at test time, in the training data, or around the deployed system. Its place is one branch of the survey's Figure 3; see the [classification guide](docs/classification-guide.md).

Not eligible: ordinary training epochs or feed-forward cascades with independent stages presented as "iterative"; loops with no medical imaging application; and papers that only mention iteration in passing. Reviews are listed only under **S. Surveys**, as background.

## The taxonomy is closed

There are exactly six classes (five loop families plus Surveys), each with a fixed list of branches, in [`config/taxonomy.json`](config/taxonomy.json). A row whose class or branch is not in that file fails validation; it never creates a new heading. If a paper does not fit, leave `taxonomy_class` and `taxonomy_subcategory` empty and explain why in `notes`; the importer will queue it for a maintainer. Changing the taxonomy needs a maintainer-approved PR to `config/taxonomy.json` that follows a change to the survey's Figure 3, updates `tests/test_taxonomy.py` and re-runs `python scripts/taxonomy.py --write`.

## Code links

Link only a repository released by the paper's authors, and say where the link came from in `code_status`:

| `code_status` | Meaning | `official_code` |
| --- | --- | :-: |
| `Linked from the official paper page` | The publisher, proceedings or arXiv page links the repository. | `Yes` |
| `Curated record` | The repository was in the survey's curated code field. | `Yes` |
| `Survey follow-up link (Table S10)` | Identified in the survey's follow-up checks; shown with an asterisk. | `No` |
| `Repository without method code (Table S10)` | The repository exists but holds no method code. Put the URL in `project_link`, not `code_link`. | `No` |
| `Project page only` | A project page but no code. Put the URL in `project_link`. | `No` |
| `No project-specific URL found` | Nothing found. Leave `code_link` empty. | `No` |
| `Code link supplied in the issue` | Set by the issue bot; the reviewer must confirm it before merging. | `Yes` |

Third-party re-implementations are not listed.

## Column reference

| Column | Required | Description |
| --- | :---: | --- |
| `paper_name` | ✅ | Exact title, as on the publisher or arXiv record. |
| `paper_link` | ✅ | DOI link or official proceedings page; arXiv for preprints. |
| `code_link` | | Repository URL (see *Code links*). GitHub links get a star badge automatically. |
| `year` | ✅ | Four-digit publication year (the proceedings year for published papers). |
| `authors` | | `First Last; First Last; ...` or `Last, First; ...` |
| `venue` | | Full venue, e.g. `Medical Image Analysis, vol. 95, p. 103201`. |
| `venue_short` | | Short label shown in the README, e.g. `MedIA`, `MICCAI`, `arXiv`. The year is appended automatically. |
| `publication_status` | | `Published`, `Accepted` or `Preprint`. |
| `taxonomy_class` | ✅ | One of the six classes in `config/taxonomy.json`. |
| `taxonomy_subcategory` | ✅ | A branch **of that class** from the survey's Figure 3. |
| `classification_confidence` | | `high`, `medium` or `low`. `low` always goes to review. |
| `model_name` | ✅ | Name shown in bold in the README. |
| `source_primary_category` | | The raw category label of a curated record, kept for traceability. It never decides a heading. |
| `loop_mechanism` | | What is iterated and what closes the loop, in one sentence. |
| `loop_level` | | The source record's L1–L4 label (metadata only, not used in the analysis). |
| `modality` | | Imaging modality, shown in the README. |
| `task` | | Short task description, shown in the README. |
| `methodology_summary` | | One or two sentences on the method. |
| `dataset`, `evaluation_metrics` | | As reported by the paper; `n/r` if not reported. |
| `stability_evidence` | | Any reported convergence, stability, collapse or degradation result. |
| `external_validation` | | External or prospective validation, if any. |
| `doi` | | DOI without the `https://doi.org/` prefix. |
| `arxiv_id` | | arXiv identifier, e.g. `2409.11299`. |
| `project_link` | | Project page, or a repository without method code. |
| `code_status` | | See *Code links*. |
| `official_code` | | `Yes` or `No` (see *Code links*). |
| `survey_ref` | | Reference number in the survey, e.g. `[24]`, for records the survey covers. |
| `context_level` | | `Yes` if the survey's curation audit judged the record context-level rather than core evidence (shown as ‡). |
| `verification_status` | | How the metadata was checked. |
| `notes` | | Curation notes (not shown in the README). |
| `suggested_by` | | GitHub username of the person who suggested the paper. Shown on the website; filled in automatically for papers added from issues. |

## Corrections

Wrong venue, dead link, or a preprint that has since been published? Open an issue or edit the row directly. Corrections are as valuable as additions.
