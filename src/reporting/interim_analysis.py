"""Materialize report-ready empirical summaries from audited result files.

This module is deliberately separate from Markdown rendering: all arithmetic and
selection of empirical facts happens here and is saved as CSV/JSON.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

from src.utils.config import ROOT, load_config, write_json


OUT = ROOT / "results" / "tables" / "interim_report"
FACTOR_NAMES = ["MKT", "SMB", "HML", "RMW", "CMA"]


def _save(frame: pd.DataFrame, name: str, out: Path = OUT) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / name, index=False)
    return frame


def _records(frame: pd.DataFrame) -> list[dict]:
    # Preserve very small p-values (for example 1e-12 GRS results) rather than
    # accepting pandas' default ten-decimal JSON rounding.
    return json.loads(frame.to_json(orient="records", double_precision=15))


def build_interim_summaries(
    results_root: Path = ROOT / "results",
    processed_root: Path = ROOT / "data/processed",
    manifest_path: Path = ROOT / "production_manifest.json",
    out: Path = OUT,
    title: str = "Interim Empirical Results Report — Post-Audit, Pre-Canonical Production Run",
) -> dict:
    cfg = load_config()
    labels = {family: info["label"] for family, info in cfg["families"].items()}
    manifest = json.loads(manifest_path.read_text())
    grs_family = manifest["selected_grs_family"] if isinstance(manifest["selected_grs_family"], str) else manifest["selected_grs_family"]["portfolio_family_id"]
    cross = pd.read_csv(results_root / "two_pass/cross_sectional_results.csv")
    errors = pd.read_csv(results_root / "two_pass/pricing_errors.csv")
    hml = pd.read_csv(results_root / "two_pass/hml_diagnostics.csv")
    metadata = pd.read_csv(processed_root / "grid_metadata.csv")
    fm = pd.read_csv(results_root / "fama_macbeth/summary_statistics/all.csv")
    effective = pd.read_csv(results_root / "fama_macbeth/effective_samples.csv")
    time_series = pd.read_csv(results_root / f"time_series/{grs_family}/portfolio_regressions_all.csv")
    grs = pd.read_csv(results_root / f"time_series/{grs_family}/grs_results.csv")
    factors = pd.read_csv(processed_root / "factors.csv")
    factors["date"] = pd.PeriodIndex(factors.date, freq="M")

    fit = cross.groupby(["family", "sample", "model"], as_index=False).agg(
        cross_sectional_R2=("cross_sectional_R2", "first"), n_assets=("n_assets", "first"))
    err = errors.groupby(["family", "sample", "model"], as_index=False).agg(
        mean_abs_pricing_error=("abs_pricing_error", "mean"),
        max_abs_pricing_error=("abs_pricing_error", "max"))
    fit = fit.merge(err, on=["family", "sample", "model"], validate="one_to_one")
    r2 = fit.pivot(index=["family", "sample"], columns="model", values="cross_sectional_R2").reset_index()
    mae = fit.pivot(index=["family", "sample"], columns="model", values="mean_abs_pricing_error").reset_index()
    mx = fit.pivot(index=["family", "sample"], columns="model", values="max_abs_pricing_error").reset_index()
    family = r2[["family", "sample"]].copy()
    family["family_label"] = family.family.map(labels)
    for model in ("CAPM", "FF3", "FF5"):
        family[f"{model}_R2"] = r2[model]
        family[f"{model}_MAE_pct_month"] = mae[model] * 100
        family[f"{model}_max_abs_error_pct_month"] = mx[model] * 100
    family["FF3_minus_CAPM_R2"] = family.FF3_R2-family.CAPM_R2
    family["FF5_minus_CAPM_R2"] = family.FF5_R2-family.CAPM_R2
    family = _save(family, "cross_family_fit.csv", out)

    bm_summary = family.loc[family.family == "size_book_to_market"].copy()
    _save(bm_summary, "size_bm_model_summary.csv", out)
    bm_errors = errors.loc[(errors.family == "size_book_to_market") & errors.model.isin(["CAPM", "FF5"])].copy()
    bm_errors = bm_errors.merge(metadata[["asset_id", "size_label", "characteristic_label"]],
        left_on="asset", right_on="asset_id", validate="many_to_one")
    bm_errors["portfolio_label"] = bm_errors.size_label + " / " + bm_errors.characteristic_label
    bm_errors["actual_pct_month"] = bm_errors.actual_mean_return*100
    bm_errors["predicted_pct_month"] = bm_errors.predicted_mean_return*100
    bm_errors["pricing_error_pct_month"] = bm_errors.pricing_error*100
    bm_largest = bm_errors.sort_values("abs_pricing_error", ascending=False).groupby(
        ["sample", "model"], sort=False).head(5)
    _save(bm_largest[["sample", "model", "asset", "portfolio_label", "actual_pct_month",
        "predicted_pct_month", "pricing_error_pct_month"]], "size_bm_largest_pricing_errors.csv", out)

    global_errors = errors.merge(metadata[["asset_id", "size_label", "characteristic_label"]],
        left_on="asset", right_on="asset_id", validate="many_to_one")
    global_errors["family_label"] = global_errors.family.map(labels)
    global_errors["portfolio_label"] = global_errors.size_label + " / " + global_errors.characteristic_label
    global_errors["pricing_error_pct_month"] = global_errors.pricing_error*100
    global_largest = global_errors.loc[global_errors.model == "CAPM"].sort_values(
        "abs_pricing_error", ascending=False).groupby("sample").head(10)
    _save(global_largest[["sample", "family", "family_label", "asset", "portfolio_label",
        "pricing_error_pct_month"]], "largest_capm_errors_across_families.csv", out)

    hml_report = hml.copy()
    hml_report["family_label"] = hml_report.family.map(labels)
    hml_report["lambda_HML_pct_month"] = hml_report.lambda_HML*100
    hml_report["significant_5pct"] = hml_report.HML_p_value < .05
    _save(hml_report, "hml_diagnostics.csv", out)

    lambda_summary = cross.groupby(["sample", "model", "coefficient"], as_index=False).agg(
        median_estimate=("estimate", "median"), mean_estimate=("estimate", "mean"),
        min_estimate=("estimate", "min"), max_estimate=("estimate", "max"),
        significant_5pct=("p_value", lambda values: int((values < .05).sum())), families=("family", "nunique"))
    for col in ["median_estimate", "mean_estimate", "min_estimate", "max_estimate"]:
        lambda_summary[col.replace("estimate", "pct_month")] = lambda_summary[col]*100
    _save(lambda_summary, "two_pass_lambda_summary.csv", out)

    sample_specs = manifest["headline_sample_periods"]
    factor_rows = []
    for sample, spec in sample_specs.items():
        use = factors.loc[factors.date.between(pd.Period(spec["actual_start"], "M"), pd.Period(spec["actual_end"], "M"))]
        for factor in FACTOR_NAMES:
            values = use[factor].dropna()
            se = values.std(ddof=1)/np.sqrt(len(values))
            factor_rows.append({"sample": sample, "factor": factor, "mean_pct_month": values.mean()*100,
                "t_stat": values.mean()/se, "std_pct_month": values.std(ddof=1)*100, "T": len(values)})
    factor_premia = _save(pd.DataFrame(factor_rows), "historical_factor_premia.csv", out)

    fm_report = fm.copy()
    fm_report["mean_lambda_pct_month"] = fm_report.mean_lambda*100
    fm_report["fm_standard_error_pct_month"] = fm_report.fm_standard_error*100
    fm_report["hac_standard_error_pct_month"] = fm_report.hac_standard_error*100
    fm_report["significant_fm_5pct"] = fm_report.fm_p_value < .05
    _save(fm_report, "fama_macbeth_summary.csv", out)
    _save(effective, "fama_macbeth_effective_samples.csv", out)

    diagnostics = []
    for path in sorted((results_root / "fama_macbeth/lambda_diagnostics").glob("*.csv")):
        frame = pd.read_csv(path)
        diagnostics.append(frame)
    lambda_diag = pd.concat(diagnostics, ignore_index=True)
    for col in ["mean_lambda", "std_lambda", "min_lambda", "max_lambda"]:
        lambda_diag[col+"_pct_month"] = lambda_diag[col]*100
    lambda_diag["positive_minus_negative_share"] = lambda_diag.share_positive-lambda_diag.share_negative
    _save(lambda_diag, "lambda_time_variation.csv", out)

    alpha = time_series.copy()
    alpha["abs_alpha"] = alpha.alpha.abs()
    alpha["abs_alpha_t"] = alpha.alpha_t.abs()
    alpha_summary = alpha.groupby(["portfolio_family", "sample", "model"], as_index=False).agg(
        mean_abs_alpha=("abs_alpha", "mean"), max_abs_alpha=("abs_alpha", "max"),
        mean_abs_alpha_t=("abs_alpha_t", "mean"), max_abs_alpha_t=("abs_alpha_t", "max"),
        significant_alpha_count=("alpha_p", lambda values: int((values < .05).sum())), n_assets=("portfolio", "count"))
    alpha_summary["mean_abs_alpha_pct_month"] = alpha_summary.mean_abs_alpha*100
    alpha_summary["max_abs_alpha_pct_month"] = alpha_summary.max_abs_alpha*100
    _save(alpha_summary, "alpha_model_summary.csv", out)
    alpha = alpha.merge(metadata[["asset_id", "size_label", "characteristic_label"]],
        left_on="portfolio", right_on="asset_id", validate="many_to_one")
    alpha["portfolio_label"] = alpha.size_label + " / " + alpha.characteristic_label
    alpha["alpha_pct_month"] = alpha.alpha*100
    extremes = []
    for _, group in alpha.groupby(["sample", "model"]):
        extremes.extend([group.loc[group.alpha_t.idxmax()], group.loc[group.alpha_t.idxmin()]])
    alpha_extremes = pd.DataFrame(extremes)
    _save(alpha_extremes[["portfolio_family", "sample", "model", "portfolio", "portfolio_label",
        "alpha_pct_month", "alpha_t", "alpha_p"]], "alpha_extremes.csv", out)

    grs_report = grs.copy()
    grs_report["reject_5pct"] = grs_report.p_value < .05
    _save(grs_report, "grs_results.csv", out)

    mean_fit = family.groupby("sample", as_index=False).agg(
        CAPM_mean_R2=("CAPM_R2", "mean"), FF3_mean_R2=("FF3_R2", "mean"), FF5_mean_R2=("FF5_R2", "mean"),
        CAPM_mean_MAE_pct=("CAPM_MAE_pct_month", "mean"), FF3_mean_MAE_pct=("FF3_MAE_pct_month", "mean"),
        FF5_mean_MAE_pct=("FF5_MAE_pct_month", "mean"))
    breadth = family.groupby("sample", as_index=False).agg(
        FF3_improves_R2_families=("FF3_minus_CAPM_R2", lambda x: int((x > 0).sum())),
        FF5_improves_R2_families=("FF5_minus_CAPM_R2", lambda x: int((x > 0).sum())))
    hml_summary = hml_report.groupby("sample", as_index=False).agg(
        positive_HML_families=("lambda_HML", lambda x: int((x > 0).sum())),
        significant_HML_families=("significant_5pct", "sum"), median_HML_pct=("lambda_HML_pct_month", "median"),
        median_delta_R2=("delta_R2", "median"), min_delta_R2=("delta_R2", "min"), max_delta_R2=("delta_R2", "max"))
    facts = {
        "title": title,
        "selected_grs_family": grs_family,
        "headline_samples": manifest["headline_sample_periods"],
        "mean_cross_family_fit": _records(mean_fit),
        "improvement_breadth": _records(breadth),
        "size_bm_summary": _records(bm_summary),
        "size_bm_largest_errors": _records(bm_largest),
        "largest_capm_errors": _records(global_largest),
        "hml_summary": _records(hml_summary),
        "hml_diagnostics": _records(hml_report),
        "two_pass_lambda_summary": _records(lambda_summary),
        "historical_factor_premia": _records(factor_premia),
        "fm_spec8": _records(fm_report.loc[(fm_report.specification == 8) & (fm_report.coefficient != "intercept")]),
        "fm_all": _records(fm_report),
        "fm_effective_spec8": _records(effective.loc[effective.specification == 8]),
        "lambda_diagnostics": _records(lambda_diag),
        "alpha_summary": _records(alpha_summary),
        "alpha_extremes": _records(alpha_extremes),
        "grs": _records(grs_report),
        "source_files": {
            "two_pass": str(results_root / "two_pass/cross_sectional_results.csv"),
            "pricing_errors": str(results_root / "two_pass/pricing_errors.csv"),
            "hml": str(results_root / "two_pass/hml_diagnostics.csv"),
            "fm": str(results_root / "fama_macbeth/summary_statistics/all.csv"),
            "fm_effective_samples": str(results_root / "fama_macbeth/effective_samples.csv"),
            "monthly_lambdas": str(results_root / "fama_macbeth/monthly_lambdas/all.csv"),
            "lambda_diag_univariate_earlier": str(results_root / "fama_macbeth/lambda_diagnostics/combined_univariate__earlier.csv"),
            "lambda_diag_univariate_post_gfc": str(results_root / "fama_macbeth/lambda_diagnostics/combined_univariate__post_gfc.csv"),
            "lambda_diag_industries_earlier": str(results_root / "fama_macbeth/lambda_diagnostics/industries_49__earlier.csv"),
            "lambda_diag_industries_post_gfc": str(results_root / "fama_macbeth/lambda_diagnostics/industries_49__post_gfc.csv"),
            "time_series": str(results_root / f"time_series/{grs_family}/portfolio_regressions_all.csv"),
            "grs": str(results_root / f"time_series/{grs_family}/grs_results.csv"),
            "factors": str(processed_root / "factors.csv"),
            "grid_metadata": str(processed_root / "grid_metadata.csv"),
            "production_metadata": str(manifest_path),
        },
    }
    source_paths = [Path(value) for value in facts["source_files"].values()]
    facts["source_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    write_json(out / "interim_empirical_facts.json", facts)
    return facts


if __name__ == "__main__":
    build_interim_summaries()
