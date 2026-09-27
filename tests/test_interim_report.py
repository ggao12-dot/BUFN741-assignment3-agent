from pathlib import Path
import json
import re
import pandas as pd

from src.utils.config import ROOT


REPORT = ROOT / "reports/assignment3_empirical_results_report.md"
FACTS = ROOT / "results/tables/interim_report/interim_empirical_facts.json"


def test_interim_report_answers_all_nine_questions():
    text = REPORT.read_text()
    assert "Interim Empirical Results Report — Post-Audit, Pre-Canonical Production Run" in text
    section = text.split("## 7. Answers to Analysis and Interpretation Questions", 1)[1]
    assert len(re.findall(r"^### [1-9]\. ", section, flags=re.MULTILINE)) == 9


def test_interim_report_image_links_resolve():
    text = REPORT.read_text()
    targets = re.findall(r"!\[[^]]*\]\(([^)]+)\)", text)
    assert len(targets) >= 4
    assert all((REPORT.parent / target).resolve().is_file() for target in targets)


def test_interim_key_values_trace_to_results():
    text = REPORT.read_text()
    cross = pd.read_csv(ROOT / "results/tables/interim_report/cross_family_fit.csv")
    bm = cross[(cross.family == "size_book_to_market") & (cross["sample"] == "earlier")].iloc[0]
    assert f"R² is {bm.CAPM_R2:.3f}" in text
    grs = pd.read_csv(ROOT / "results/time_series/size_momentum/grs_results.csv")
    post_capm = grs[(grs["sample"] == "post_gfc") & (grs.model == "CAPM")].iloc[0]
    assert f"CAPM p = {post_capm.p_value:.4f}" in text


def test_interim_facts_preserve_small_grs_pvalues():
    facts = json.loads(FACTS.read_text())
    earlier = [row["p_value"] for row in facts["grs"] if row["sample"] == "earlier"]
    assert min(earlier) > 0 and max(earlier) < 1e-9


def test_interim_figures_are_distinct_required_outputs():
    paths = [
        ROOT / "results/figures/interim_report/size_bm_pricing_four_panel.png",
        ROOT / "results/figures/interim_report/fm_spec8_lambdas_four_panel.png",
        ROOT / "results/figures/time_series/size_momentum__earlier__CAPM__alpha_t.png",
        ROOT / "results/figures/time_series/size_momentum__post_gfc__CAPM__alpha_t.png",
    ]
    assert all(path.stat().st_size > 10_000 for path in paths)
