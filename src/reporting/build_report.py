from __future__ import annotations

from pathlib import Path


def build_report(path: Path, facts: dict, manifest: dict) -> None:
    samples = manifest.get("headline_sample_periods", {})
    sample_rows = [f"| {name} | {value['actual_start']} | {value['actual_end']} | {value['n_months']} |" for name, value in samples.items()]
    fit_rows = [f"| {r['sample']} | {r['model']} | {r['mean']:.3f} | {r['median']:.3f} | {r['min']:.3f} | {r['max']:.3f} |" for r in facts.get("cross_sectional_fit_summary", [])]
    hml_rows = [f"| {r['sample']} | {r['mean_lambda_HML']:.5f} | {r['median_delta_R2']:.3f} | {r['significant_at_5pct']} / {r['families']} |" for r in facts.get("hml_summary", [])]
    grs_rows = [f"| {r['sample']} | {r['model']} | {r['grs_F']:.3f} | {r['df1']}, {r['df2']} | {r['p_value']:.4g} |" for r in facts.get("grs_statistics", [])]
    alpha_rows = [f"| {r['sample']} | {r['model']} | {r['portfolio']} | {r['alpha']:.5f} | {r['alpha_t']:.2f} |" for r in facts.get("alpha_patterns", [])]
    fm_dates = [r for r in facts.get("fm_effective_samples", []) if r["specification"] == 8]
    fm_date_rows = [f"| {r['universe']} | {r['sample']} | {r['first_return_month']} | {r['last_return_month']} | {r['T']} |" for r in fm_dates]
    fm_rows = [f"| {r['universe']} | {r['sample']} | {r['coefficient']} | {r['mean_lambda']:.5f} | {r['fm_t_stat']:.2f} | {r['hac_t_stat']:.2f} |" for r in facts.get("fm_specification_8", [])]
    lines = ["# Assignment 3: Empirical Asset-Pricing Tests", "",
        "## 1. Objective", "", "This report compares two-pass, Fama–MacBeth, and time-series/GRS evidence using value-weighted Kenneth French portfolios.", "",
        "## 2. Data and test assets", "", "Returns are monthly decimals; portfolio excess returns are constructed once by subtracting RF in the processed-data layer.", "",
        "## 3. Sample construction", "", "Common factor/asset boundaries used in the headline analyses:", "",
        "| Sample | Actual start | Actual end | Months |", "|---|---:|---:|---:|", *sample_rows, "",
        "## 4. Models and methodology", "", "CAPM, FF3, and FF5 definitions are shared across all tests. Rolling betas use months t-35 through t and predict t+1.", "",
        "## 5. Test I — Two-pass cross-sectional tests", "", "Cross-sectional R² across the eleven families:", "",
        "| Sample | Model | Mean | Median | Min | Max |", "|---|---:|---:|---:|---:|---:|", *fit_rows, "",
        "## 6. Cross-sectional pricing plots", "", "See `results/figures/two_pass/`.", "",
        "## 7. HML incremental-pricing evidence", "", "The table reports structured evidence only; an insignificant price in one cross section is not labeled redundancy.", "",
        "| Sample | Mean HML price | Median ΔR² | p < 5% |", "|---|---:|---:|---:|", *hml_rows, "",
        "## 8. Test II — Fama–MacBeth tests", "", "Conventional FM inference is primary; HAC inference is reported separately. Effective specification-8 return samples are:", "",
        "| Universe | Sample | First return | Last return | T |", "|---|---|---:|---:|---:|", *fm_date_rows, "",
        "Specification-8 factor prices:", "", "| Universe | Sample | Factor | Mean lambda | FM t | HAC t |", "|---|---|---|---:|---:|---:|", *fm_rows, "",
        "## 9. Dynamics of monthly factor prices", "", "Specification-8 lambda figures report prices, not portfolio betas.", "",
        "## 10. Characteristic portfolios versus industries", "", "The corresponding compact tables and structured summaries permit direct comparison.", "",
        "## 11. Test III — Time-series regressions and GRS", "", f"Selected family: `{manifest.get('selected_grs_family')}`.", "",
        "| Sample | Model | GRS F | df | p-value |", "|---|---:|---:|---:|---:|", *grs_rows, "",
        "## 12. Alpha-grid evidence", "", "Largest absolute individual alpha t-statistic within each model/sample:", "",
        "| Sample | Model | Portfolio | Alpha | t-stat |", "|---|---:|---|---:|---:|", *alpha_rows, "",
        "## 13. Comparison across empirical testing frameworks", "", "Cross-sectional pricing errors, time-series alphas, and GRS joint restrictions answer distinct questions and are not ranked mechanically.", "",
        "## 14. Limitations", "", "Betas are fixed-window estimates; errors-in-variables, changing exposures, multiple testing, and sensitivity to the 36-month window remain important.", "",
        "## 15. Conclusions", "", "Conclusions should be drawn from `results/interpretation_facts.json`, not unsupported prose.", "",
        "## 16. Appendix / artifact references", "", "See `production_manifest.json` for a complete artifact inventory."]
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text("\n".join(lines)+"\n")
