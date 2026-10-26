#!/usr/bin/env python3
"""Build data/papers.csv from the survey's curated record table (one-off, re-runnable).

Source:     data/source/loop_medical_papers_survey_ready.csv  (the 56 curated records, unchanged)
Reference:  the manuscript "Looped Models for Medical Imaging: A Survey of Iterative Architectures,
            Test-Time Adaptation, and Feedback" (main text + supplementary).

Every decision is explicit and cited, nothing is inferred from keywords:
  - each source row is matched to its manuscript reference number by DOI or arXiv identifier
    (REFS below, taken from the manuscript bibliography); an unmatched or doubly matched row stops
    the script;
  - its family and branch are the leaf of the manuscript's Figure 3 that cites that reference
    (PLACEMENT); the surveys are the manuscript's survey class (Supplementary Table S1);
  - code links are Supplementary Table S10 (CODE), with the table's own distinction between a link
    in the curated code field and one identified during follow-up; repositories that Table S10 says
    contain no method code are kept as project links, never shown as code;
  - venue, year and status follow Supplementary Tables S2-S4 and the bibliography (VENUE);
  - display names (NAME) use the method name the record or manuscript gives; where the record has
    none ("Not named"), a short descriptive label is used and recorded in the notes.

Usage:  python scripts/migrations/2026_10_initial_import.py [--write]
Without --write it only validates and prints the report. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from build_readme import FIELDS, CSV_PATH, QUEUE_FIELDS, QUEUE_PATH, validate, validate_queue  # noqa: E402
from taxonomy import load as load_taxonomy  # noqa: E402

SOURCE = ROOT / "data" / "source" / "loop_medical_papers_survey_ready.csv"
REPORT = ROOT / "docs" / "initial-import-report.md"

R, U, T, D, H, S = ("Recurrent, recursive & equilibrium", "Unrolled & data-consistency reconstruction",
                    "Test-time loops", "Data-feedback training loops", "Human, deployment & lifelong loops", "Surveys")

# ref -> identifier from the manuscript bibliography (DOI, or arXiv ID when the record has no DOI)
REFS = {
    1: "10.1109/TMI.2018.2865356", 6: "10.1016/j.media.2020.101907", 7: "10.1038/s41467-021-26216-9",
    8: "10.1038/s42256-019-0018-3", 9: "10.1038/s41467-023-42396-y", 10: "10.1007/978-3-031-43901-8_49",
    16: "10.1016/j.imed.2021.03.003", 17: "2503.07097", 18: "10.1016/j.media.2021.102062", 19: "2310.14230",
    20: "2312.17004", 21: "10.1145/3785663", 22: "2306.04750", 24: "10.1117/1.JMI.6.1.014006",
    25: "10.1007/s00521-022-07419-7", 26: "2108.00622", 27: "10.1109/TMI.2018.2863670",
    31: "10.1016/j.media.2019.01.005", 32: "2111.09639", 38: "2506.18070", 48: "10.1016/j.compbiomed.2025.110658",
    49: "10.1016/j.compbiomed.2022.105831", 50: "10.1002/mp.70185", 51: "10.1088/1361-6560/ac6cc2",
    52: "2306.11238", 53: "2405.05564", 54: "10.1016/j.media.2024.103331", 55: "10.1145/3503161.3548068",
    56: "2301.10365", 57: "2503.16616", 58: "2506.23705", 59: "proceedings.mlr.press/v172/tomar22a",
    60: "10.1109/CVPR52733.2024.01063", 61: "2504.02008", 62: "2506.05221", 63: "2410.02523", 64: "2409.11299",
    65: "2502.02341", 66: "2510.10052", 67: "10.2196/90693", 68: "2006.16806", 69: "10.1007/978-3-031-16452-1_14",
    70: "10.1016/j.media.2022.102656", 71: "2508.09014", 72: "2304.04441", 73: "10.3389/fphys.2026.1755067",
    74: "10.1109/TMI.2022.3217501", 75: "2211.13440", 76: "10.1109/TMI.2020.3048055",
    77: "10.1007/s10278-024-01037-6", 78: "Liao_Iteratively-Refined_Interactive_3D", 79: "2408.01620",
    80: "2603.14496", 81: "10.1016/j.media.2023.102862", 82: "2603.05860", 83: "2607.11175",
}

# ref -> (family, Figure 3 branch). Figure 3: "Loop-centered classification of the 49 primary method
# and application records"; surveys: Supplementary Table S1 survey class ("Background only", Fig. S1).
PLACEMENT = {
    24: (R, "Recurrent conv. segmentation"), 25: (R, "Recurrent conv. segmentation"),
    48: (R, "Recursive transformer U-Net"), 27: (R, "Recurrent dynamic MRI recon."),
    26: (R, "Recurrent mask refinement"), 49: (R, "Deep equilibrium models"), 50: (R, "Deep equilibrium models"),
    1: (U, "Weight-shared unrolling"), 31: (U, "Recurrent inference machines"),
    51: (U, "Recurrent inference machines"), 32: (U, "Recurrent variational network"),
    52: (U, "Multi-prior, edge, alignment DUNs"), 53: (U, "Multi-prior, edge, alignment DUNs"),
    54: (U, "Multi-prior, edge, alignment DUNs"), 55: (U, "Multi-contrast SR unfolding"),
    56: (U, "Motion search with data consistency"),
    6: (T, "Per-image weight / norm. adaptation"), 57: (T, "Per-image weight / norm. adaptation"),
    58: (T, "Per-image weight / norm. adaptation"), 59: (T, "Input, prompt, embedding TTA"),
    60: (T, "Input, prompt, embedding TTA"), 61: (T, "Input, prompt, embedding TTA"),
    62: (T, "Input, prompt, embedding TTA"), 63: (T, "Test-time training"), 64: (T, "Test-time training"),
    65: (T, "Test-time training"), 38: (T, "Concept-level correction"),
    66: (T, "VLM reasoning, test-time scaling"), 67: (T, "VLM reasoning, test-time scaling"),
    68: (D, "Co-training, mutual learning"), 69: (D, "Co-training, mutual learning"),
    70: (D, "Co-training, mutual learning"), 71: (D, "Co-training, mutual learning"),
    7: (D, "Self-training, distillation"), 72: (D, "Self-training, distillation"),
    73: (D, "Self-training, distillation"), 74: (D, "Pseudo-label-guided synthesis"),
    75: (D, "Training-data refinement"), 76: (D, "Active learning"), 77: (D, "Active learning"),
    78: (H, "Interactive / clinician correction"), 79: (H, "Interactive / clinician correction"),
    80: (H, "Interactive / clinician correction"), 8: (H, "HITL annotation engines"),
    81: (H, "HITL annotation engines"), 9: (H, "Post-deployment drift correction"),
    10: (H, "Continual memory replay"), 82: (H, "Self-improving agents, roadmap"),
    83: (H, "Self-improving agents, roadmap"),
    **{n: (S, "Background only") for n in (16, 17, 18, 19, 20, 21, 22)},
}

# Records the curation audit flags as context-level evidence (‡ in the manuscript).
CONTEXT_LEVEL = {67, 77, 83}

NAME = {
    1: "MoDL", 6: "Test-time adaptable NN", 7: "AIDE", 8: "H-AI-L", 9: "UPA", 10: "Atypical memory replay",
    16: "Reconstruction survey", 17: "MRI reconstruction survey", 18: "Active learning & HITL survey",
    19: "Deep active learning survey", 20: "Continual learning review", 21: "Continual learning survey",
    22: "AutoML survey", 24: "R2U-Net", 25: "R2U++", 26: "RP-Net", 27: "CRNN-MRI", 31: "RIM",
    32: "RecurrentVarNet", 38: "Training-free TTI", 48: "ReT-UNet", 49: "EDEM", 50: "DEAR-net", 51: "CIRIM",
    52: "CAMP-Net", 53: "JEO4MRI", 54: "DUN-SA", 55: "MGDUN", 56: "neuroMoCo", 57: "PTTEA",
    58: "Multi-view co-training TTA", 59: "OptTTA", 60: "VPTTA", 61: "MedSAM-TTA", 62: "SAM-TTA",
    63: "Med-TTT", 64: "TTT-UNet", 65: "4D TTT interpolation", 66: "ViTAR", 67: "Medical test-time scaling",
    68: "UMCT", 69: "SLC-Net", 70: "Semi-CML", 71: "UC-Seg", 72: "DUST", 73: "SDBS-Net", 74: "SA-CPS",
    75: "Iterative Data Refinement", 76: "Uncertainty AL", 77: "Brain-tumor AL", 78: "Interactive MARL",
    79: "MedUHIP", 80: "CoWTalk", 81: "HAL-IA", 82: "MACRO", 83: "Self-evolving clinical systems",
}
# Display labels that are not the record's own method name (the record says "Not named", or gives a
# descriptive phrase rather than a name). The record's method name is kept in `notes`.
DESCRIPTIVE_NAME = {6, 10, 38, 58, 65, 67, 76, 77, 78, 83, 16, 17, 18, 19, 20, 21, 22}

# The manuscript's bibliography gives a fuller or newer title than the curated record.
TITLE = {
    10: "Memory Replay for Continual Medical Image Segmentation through Atypical Sample Selection",
    20: "Continual learning in medical image analysis: A comprehensive review of recent advancements and future prospects",
    67: "Model and Task-Aware Test-Time Scaling Strategies for Large Language and Vision-Language Models in Medicine: Evaluation Study",
    69: "Semi-Supervised Medical Image Segmentation Using Cross-Model Pseudo-Supervision with Shape Awareness and Local Context Constraints",
}

# ref -> (venue, short venue, year, status) from Supplementary Tables S2-S4 and the bibliography.
VENUE = {
    1: ("IEEE Transactions on Medical Imaging", "IEEE TMI", 2018, "Published"),
    6: ("Medical Image Analysis", "MedIA", 2021, "Published"),
    7: ("Nature Communications", "Nat. Commun.", 2021, "Published"),
    8: ("Nature Machine Intelligence", "Nat. Mach. Intell.", 2019, "Published"),
    9: ("Nature Communications, vol. 14, p. 6608", "Nat. Commun.", 2023, "Published"),
    10: ("Medical Image Computing and Computer-Assisted Intervention (MICCAI)", "MICCAI", 2023, "Published"),
    16: ("Intelligent Medicine", "Intell. Med.", 2021, "Published"),
    17: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    18: ("Medical Image Analysis, vol. 71, p. 102062", "MedIA", 2021, "Published"),
    19: ("Medical Image Analysis, vol. 95, p. 103201", "MedIA", 2024, "Published"),
    20: ("Medical Image Analysis, vol. 106, p. 103730", "MedIA", 2025, "Published"),
    21: ("ACM Computing Surveys", "ACM CSUR", 2026, "Published"),
    22: ("arXiv preprint", "arXiv", 2023, "Preprint"),
    24: ("Journal of Medical Imaging", "J. Med. Imaging", 2019, "Published"),
    25: ("Neural Computing and Applications", "Neural Comput. Appl.", 2022, "Published"),
    26: ("IEEE/CVF International Conference on Computer Vision (ICCV), pp. 3918–3928", "ICCV", 2021, "Published"),
    27: ("IEEE Transactions on Medical Imaging", "IEEE TMI", 2019, "Published"),
    31: ("Medical Image Analysis", "MedIA", 2019, "Published"),
    32: ("IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)", "CVPR", 2022, "Published"),
    38: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    48: ("Computers in Biology and Medicine", "Comput. Biol. Med.", 2025, "Published"),
    49: ("Computers in Biology and Medicine", "Comput. Biol. Med.", 2022, "Published"),
    50: ("Medical Physics", "Med. Phys.", 2025, "Published"),
    51: ("Physics in Medicine & Biology", "Phys. Med. Biol.", 2022, "Published"),
    52: ("arXiv preprint", "arXiv", 2023, "Preprint"),
    53: ("arXiv preprint", "arXiv", 2024, "Preprint"),
    54: ("Medical Image Analysis", "MedIA", 2025, "Published"),
    55: ("ACM Multimedia (ACM MM)", "ACM MM", 2022, "Published"),
    56: ("arXiv preprint", "arXiv", 2023, "Preprint"),
    57: ("IEEE/CVF International Conference on Computer Vision (ICCV 2025)", "ICCV", 2025, "Published"),
    58: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    59: ("Medical Imaging with Deep Learning (MIDL 2022), PMLR 172:1192–1217", "MIDL", 2022, "Published"),
    60: ("IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR 2024)", "CVPR", 2024, "Published"),
    61: ("IEEE/CVF International Conference on Computer Vision (ICCV 2025)", "ICCV", 2025, "Published"),
    62: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    63: ("arXiv preprint", "arXiv", 2024, "Preprint"),
    64: ("Medical Imaging with Deep Learning (MIDL 2026), PMLR 315:3679–3703; earlier version at the NeurIPS 2024 AIM-FM workshop",
         "MIDL", 2026, "Published"),
    65: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    66: ("arXiv preprint", "arXiv", 2025, "Preprint"),
    67: ("Journal of Medical Internet Research, vol. 28, e90693", "JMIR", 2026, "Published"),
    68: ("IEEE/CVF Winter Conference on Applications of Computer Vision (WACV)", "WACV", 2020, "Published"),
    69: ("Medical Image Computing and Computer-Assisted Intervention (MICCAI)", "MICCAI", 2022, "Published"),
    70: ("Medical Image Analysis", "MedIA", 2023, "Published"),
    71: ("IEEE Transactions on Image Processing, vol. 34, pp. 5543–5556", "IEEE TIP", 2025, "Published"),
    72: ("Biomedical Signal Processing and Control, vol. 94, p. 106355", "BSPC", 2024, "Published"),
    73: ("Frontiers in Physiology, vol. 17, p. 1755067", "Front. Physiol.", 2026, "Published"),
    74: ("IEEE Transactions on Medical Imaging", "IEEE TMI", 2023, "Published"),
    75: ("arXiv preprint", "arXiv", 2022, "Preprint"),
    76: ("IEEE Transactions on Medical Imaging", "IEEE TMI", 2021, "Published"),
    77: ("Journal of Imaging Informatics in Medicine", "J. Imaging Inform. Med.", 2024, "Published"),
    78: ("IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)", "CVPR", 2020, "Published"),
    79: ("arXiv preprint", "arXiv", 2024, "Preprint"),
    80: ("arXiv preprint", "arXiv", 2026, "Preprint"),
    81: ("Medical Image Analysis", "MedIA", 2023, "Published"),
    82: ("arXiv preprint", "arXiv", 2026, "Preprint"),
    83: ("arXiv preprint", "arXiv", 2026, "Preprint"),
}

# Paper links from the bibliography: DOI where one exists, else the proceedings or arXiv page.
LINK_OVERRIDE = {
    59: "https://proceedings.mlr.press/v172/tomar22a.html",
    64: "https://proceedings.mlr.press/v315/zhou26a.html",
    71: "https://doi.org/10.1109/TIP.2025.3599783",
}
DOI_FROM_BIB = {  # records whose curated row lacks the DOI the bibliography gives
    19: "10.1016/j.media.2024.103201", 20: "10.1016/j.media.2025.103730", 26: "10.1109/ICCV48922.2021.00389",
    32: "10.1109/CVPR52688.2022.00081", 57: "10.1109/ICCV51701.2025.02074", 61: "10.1109/ICCV51701.2025.01867",
    68: "10.1109/WACV45572.2020.9093608", 71: "10.1109/TIP.2025.3599783", 72: "10.1016/j.bspc.2024.106355",
    78: "10.1109/CVPR42600.2020.00941",
}

# Supplementary Table S10. (status, url). Curated = URL in the record's curated code field;
# FOLLOW = identified during the authors' follow-up checks (asterisk in Table S10).
CUR, PAGE, FOLLOW, NOCODE, PROJECT = ("Curated record", "Linked from the official paper page",
                                      "Survey follow-up link (Table S10)",
                                      "Repository without method code (Table S10)", "Project page only")
GH = "https://github.com/"
CODE = {
    27: (CUR, GH + "cq615/CRNN-MRI"), 55: (CUR, GH + "yggame/MGDUN"), 32: (CUR, GH + "NKI-AI/direct"),
    56: (CUR, GH + "nalinimsingh/neuroMoCo"), 52: (CUR, GH + "lpzhang/CAMP-Net"),
    53: (CUR, GH + "Tsaiyue/JEO4MRI"),
    6: (CUR, GH + "neerakara/test-time-adaptable-neural-networks-for-domain-generalization"),
    63: (CUR, GH + "Jiashu-Xu/Med-TTT"), 38: (CUR, GH + "riverback/TF-TTI-XMed"),
    58: (CUR, GH + "smriti-joshi/muvi"), 62: (CUR, GH + "JianghaoWu/SAM-TTA"), 69: (CUR, GH + "igip-liu/SLC-Net"),
    74: (CUR, GH + "FeiLyu/SASSL"), 71: (CUR, GH + "taozh2017/UCSeg"), 8: (CUR, GH + "SarderLab/H-AI-L"),
    59: (PAGE, GH + "devavratTomar/OptTTA"), 60: (PAGE, GH + "Chen-Ziyang/VPTTA"),
    64: (PAGE, GH + "rongzhou7/TTT-UNet"), 21: (PAGE, GH + "BioMedIA-MBZUAI/awesome-cl-in-medical"),
    57: (PROJECT, "https://voldemort108x.github.io/pttea_seg/"),
    26: (FOLLOW, GH + "uci-cbcl/RP-Net"), 1: (FOLLOW, GH + "hkaggarwal/modl"),
    65: (FOLLOW, GH + "ChaosTheProducer/TTT4D"), 9: (FOLLOW, GH + "biomedia-mira/upa"),
    31: (FOLLOW, GH + "NKI-AI/direct"), 51: (FOLLOW, GH + "NKI-AI/direct"), 7: (FOLLOW, GH + "lich0031/AIDE"),
    66: (FOLLOW, GH + "JLINEkai/ViTAR"), 77: (FOLLOW, GH + "naddan27/ActiveLearning"),
    19: (FOLLOW, GH + "LightersWang/Awesome-Active-Learning-for-Medical-Image-Analysis"),
    61: (NOCODE, GH + "tonyckc/Test-time-Adaptation-for-Foundation-Medical-Segmentation-Model-Without-Parametric-Updates"),
    78: (NOCODE, GH + "Chuyun-Shen/Interactive-Medical-Image-Segmentation-with-MARL"),
    73: (NOCODE, GH + "fangchj2002/SDBS-Net"), 80: (NOCODE, GH + "HINTLab/CowTalk"),
}
CODE_NOTE = {
    31: "Code: RIM implementation in the NKI-AI DIRECT framework, not a paper-specific release (Table S10).",
    51: "Code: CIRIM implementation in the NKI-AI DIRECT framework, not a paper-specific release (Table S10).",
    32: "Code: implementation in the NKI-AI DIRECT framework, not a paper-specific release (Table S10).",
    78: "Table S10: the repository README says code is forthcoming.",
    70: "Table S2 marks a follow-up code link, but Table S10 excludes the Semi-CML archive endpoint from the link count; no link is listed here.",
    56: "Curated code URL given as www.github.com; normalised to github.com.",
    58: "Curated code URL ends in .git; normalised to the repository page.",
}

# Bibliography author lists for records whose curated author field is truncated or mis-ordered.
AUTHORS = {
    27: "Chen Qin; Jo Schlemper; Jose Caballero; Anthony N. Price; Joseph V. Hajnal; Daniel Rueckert",
    61: "K. Chen; X. Luo; T. Qin; J. Liu; H. Liu; V. H. F. Lee; H. Yan; H. Li",
    64: "R. Zhou; Z. Yuan; Z. Yan; W. Sun; K. Zhang; Y. Li; Y. Ye; X. Li; L. Sun; L. He",
    73: "H. Liu; X. Li; J. Jin; S. Zhang; Y. Fu; J. Fang; G. Wang",
}
AUTHOR_NOTE = {
    27: "Authors: the curated record lists the first author as 'Qin Chen'; the manuscript's data-quality notes give Chen Qin.",
    61: "Authors: curated record lists 'Kang Chen; et al.'; full list from the manuscript bibliography.",
    64: "Authors: curated record lists 'Rongzhou Zhou; et al.'; full list from the manuscript bibliography.",
    73: "Authors: curated record lists 'Huaxiang Liu; et al.'; full list from the manuscript bibliography.",
}
VENUE_NOTE = {
    64: "Venue: the curated record cites the NeurIPS 2024 AIM-FM workshop version; the manuscript cites the MIDL 2026 PMLR version.",
    71: "Venue: the curated record and Table S3 list the arXiv preprint; the manuscript bibliography cites the IEEE TIP 2025 version.",
    67: "Title: the curated record carries the preprint title 'Rethinking Test-Time Scaling for Medical AI: Model and Task-Aware Strategies for LLMs and VLMs'; the manuscript cites the JMIR title.",
    75: "Family: the source label 'iterative reconstruction' maps to Unrolled/DC in Table S1, but the manuscript assigns this record to data-feedback because its loop refines the training data rather than the image (Section III-A).",
}

NOT_REPORTED = {"not verified in this pass", "not named"}


def clean(v: str) -> str:
    v = " ".join((v or "").split())
    return "" if v.lower() in NOT_REPORTED else v


def match_ref(row: dict) -> list[int]:
    hay = " ".join(row.get(k, "") for k in ("doi", "arxiv_id", "paper_url", "pdf_url", "audit_official_url")).lower()
    return [n for n, ident in REFS.items() if ident.lower() in hay]


def build() -> tuple[list[dict], list[str]]:
    tax = load_taxonomy()
    with SOURCE.open(encoding="utf-8-sig", newline="") as f:
        src = list(csv.DictReader(f))
    out, problems, seen = [], [], Counter()
    for i, s in enumerate(src, start=2):
        refs = match_ref(s)
        if len(refs) != 1:
            problems.append(f"source line {i}: matched references {refs} for '{s['paper_title'][:60]}'")
            continue
        n = refs[0]
        seen[n] += 1
        cls, sub = PLACEMENT[n]
        assert tax.is_valid(cls, sub), (n, cls, sub)
        venue, short, year, status = VENUE[n]
        doi = s["doi"].strip() or DOI_FROM_BIB.get(n, "")
        code_status, url = CODE.get(n, ("No project-specific URL found", ""))
        is_repo = code_status in (CUR, PAGE, FOLLOW)
        notes = [clean(s["audit_recommended_action"])]
        if n in DESCRIPTIVE_NAME:
            notes.append(f"Display name is a descriptive label; the record's method name is "
                         f"'{clean(s['method_name']) or 'not given'}'.")
        notes += [x for x in (CODE_NOTE.get(n), AUTHOR_NOTE.get(n), VENUE_NOTE.get(n)) if x]
        if s["year"] != str(year):
            notes.append(f"Year: curated record says {s['year']}; manuscript gives {year}.")
        out.append({
            "paper_name": TITLE.get(n, " ".join(s["paper_title"].split())),
            "paper_link": LINK_OVERRIDE.get(n) or (f"https://doi.org/{doi}" if doi else f"https://arxiv.org/abs/{s['arxiv_id']}"),
            "code_link": url if is_repo else "",
            "year": str(year),
            "authors": AUTHORS.get(n, "; ".join(a.strip() for a in s["authors"].split(";") if a.strip())),
            "venue": venue,
            "venue_short": short,
            "publication_status": status,
            "taxonomy_class": cls,
            "taxonomy_subcategory": sub,
            "classification_confidence": "high",
            "model_name": NAME[n],
            "source_primary_category": s["primary_category"],
            "loop_mechanism": clean(s["loop_mechanism"]),
            "loop_level": s["loop_level"],
            "modality": clean(s["medical_modality"]),
            "task": clean(s["medical_task"]),
            "methodology_summary": clean(s["methodology_summary"]),
            "dataset": clean(s["dataset"]),
            "evaluation_metrics": clean(s["evaluation_metrics"]),
            "stability_evidence": clean(s["stability_or_collapse_evidence"]),
            "external_validation": clean(s["external_validation"]),
            "doi": doi,
            "arxiv_id": s["arxiv_id"].strip(),
            "project_link": url if code_status in (NOCODE, PROJECT) else "",
            "code_status": code_status,
            "official_code": "Yes" if code_status in (CUR, PAGE) else "No",
            "survey_ref": f"[{n}]",
            "context_level": "Yes" if n in CONTEXT_LEVEL else "",
            "verification_status": f"{clean(s['verification_status']) or 'n/r'} (curated record); classification "
                                   f"from the manuscript's {'Figure 3' if cls != S else 'survey class (Table S1)'}",
            "notes": " ".join(x for x in notes if x),
            "suggested_by": "",
        })
    missing = sorted(set(REFS) - set(seen))
    dup = sorted(n for n, k in seen.items() if k > 1)
    if missing:
        problems.append(f"references with no source row: {missing}")
    if dup:
        problems.append(f"references matched by more than one row: {dup}")
    return out, problems


def to_csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def report(rows: list[dict]) -> str:
    tax = load_taxonomy()
    expected = {R: 7, U: 9, T: 13, D: 11, H: 9, S: 7}  # manuscript Fig. 3 and Table S1
    by_cls = Counter(r["taxonomy_class"] for r in rows)
    lines = [
        "<!-- GENERATED by scripts/migrations/2026_10_initial_import.py. -->",
        "",
        "# Initial import report",
        "",
        f"Built `data/papers.csv` from the {len(rows)} curated records in "
        "[`data/source/loop_medical_papers_survey_ready.csv`](../data/source/loop_medical_papers_survey_ready.csv), "
        "the record table of the survey *Looped Models for Medical Imaging: A Survey of Iterative Architectures, "
        "Test-Time Adaptation, and Feedback*. Every row was matched to its manuscript reference number by DOI or "
        "arXiv identifier, placed on the Figure 3 leaf that cites it, and given the code link that "
        "Supplementary Table S10 reports. Nothing was inferred from keywords, and no record was dropped.",
        "",
        "## Counts against the manuscript",
        "",
        "| Family | Records here | Manuscript | Match |",
        "| --- | :-: | :-: | :-: |",
    ]
    for c in tax.classes:
        lines.append(f"| {c.letter}. {c.name} | {by_cls[c.name]} | {expected[c.name]} | "
                     f"{'✅' if by_cls[c.name] == expected[c.name] else '❌'} |")
    prim = sum(v for k, v in by_cls.items() if k != S)
    lines += ["", f"**{prim}** primary records (manuscript: 49) and **{by_cls[S]}** surveys (manuscript: 7), "
              f"{len(rows)} in total (manuscript: 56). Context-level records (‡): "
              + ", ".join(f"{r['model_name']} {r['survey_ref']}" for r in rows if r["context_level"]) + ".", ""]
    code = Counter(r["code_status"] for r in rows)
    lines += ["## Code links (Supplementary Table S10)", "", "| Status | Records |", "| --- | :-: |"]
    lines += [f"| {k} | {v} |" for k, v in sorted(code.items(), key=lambda kv: -kv[1])]
    lines += ["", "Only links from the curated code field or the official paper page are marked `official_code = Yes`. "
              "Follow-up links are shown in the README with an asterisk. Repositories that Table S10 says hold no "
              "method code are stored as `project_link` and shown as `—`.", ""]
    lines += ["## Corrections and decisions", "", "| Record | Ref. | Note |", "| --- | :-: | --- |"]
    for r in sorted(rows, key=lambda r: int(r["survey_ref"].strip("[]"))):
        n = int(r["survey_ref"].strip("[]"))
        for note in (CODE_NOTE.get(n), AUTHOR_NOTE.get(n), VENUE_NOTE.get(n)):
            if note:
                lines.append(f"| {r['model_name']} | {r['survey_ref']} | {note} |")
    lines += ["", "## Display names that are descriptive labels", "",
              "For these records the curated method name is missing (\"Not named\") or is a phrase rather than a name, "
              "so the README shows a short label. The record's own method name is kept in `notes`.", ""]
    lines += [f"- **{NAME[n]}** {f'[{n}]'}" for n in sorted(DESCRIPTIVE_NAME)]
    lines += ["", "## Source columns not carried into `data/papers.csv`", "",
              "`pdf_url`, `secondary_categories`, `flow_or_model_family`, `main_contribution`, `limitations`, "
              "`code_available` (replaced by `code_status`), `regulatory_or_governance_discussion`, `relevance_type` "
              "(replaced by the survey class), `inclusion_notes`, `source_database`, `search_query_used`, "
              "`date_accessed` and the four audit fields except `audit_recommended_action` (kept in `notes`). "
              "They remain unchanged in the source file.", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    rows, problems = build()
    problems += validate(rows) + validate_queue([], rows)
    if problems:
        print("Import failed:", *problems, sep="\n  - ", file=sys.stderr)
        return 1
    text = report(rows)
    if args.write:
        CSV_PATH.write_text(to_csv(rows, FIELDS), encoding="utf-8", newline="")
        if not QUEUE_PATH.exists():
            QUEUE_PATH.write_text(to_csv([], QUEUE_FIELDS), encoding="utf-8", newline="")
        REPORT.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {CSV_PATH.relative_to(ROOT)} ({len(rows)} rows), {REPORT.relative_to(ROOT)}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
