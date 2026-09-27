from __future__ import annotations

import pandas as pd


def build_facts(two_pass: pd.DataFrame, errors: pd.DataFrame, hml: pd.DataFrame,
                fm: pd.DataFrame, grs: pd.DataFrame, time_series: pd.DataFrame,
                fm_effective: pd.DataFrame) -> dict:
    fit = two_pass.groupby(["family", "sample", "model"], dropna=False).cross_sectional_R2.first().reset_index()
    largest = errors.sort_values("abs_pricing_error", ascending=False).groupby(["family", "sample", "model"]).head(3)
    fit_summary = fit.groupby(["sample", "model"]).cross_sectional_R2.agg(["mean", "median", "min", "max"]).reset_index()
    hml_summary = hml.groupby("sample").agg(mean_lambda_HML=("lambda_HML", "mean"),
        median_delta_R2=("delta_R2", "median"), significant_at_5pct=("HML_p_value", lambda x: int((x < .05).sum())),
        families=("family", "count")).reset_index()
    fm_significance = fm.assign(significant_at_5pct=fm.fm_p_value < .05).groupby(
        ["universe", "sample", "coefficient"], dropna=False).significant_at_5pct.sum().reset_index()
    fm_spec8 = fm.loc[(fm.specification == 8) & (fm.coefficient != "intercept")].copy()
    ts = time_series.copy(); ts["abs_alpha_t"] = ts.alpha_t.abs()
    alpha_patterns = ts.sort_values("abs_alpha_t", ascending=False).groupby(["sample", "model"]).head(1)
    return {
        "cross_sectional_fit": fit.to_dict("records"),
        "cross_sectional_fit_summary": fit_summary.to_dict("records"),
        "largest_pricing_errors": largest.to_dict("records"),
        "hml_incremental_evidence": hml.to_dict("records"),
        "hml_summary": hml_summary.to_dict("records"),
        "fm_mean_factor_prices": fm.to_dict("records"),
        "fm_specification_8": fm_spec8.to_dict("records"),
        "fm_effective_samples": fm_effective.to_dict("records"),
        "fm_significance_counts": fm_significance.to_dict("records"),
        "grs_statistics": grs.assign(reject_at_5pct=grs.p_value < .05).to_dict("records"),
        "alpha_patterns": alpha_patterns[["portfolio_family", "sample", "model", "portfolio", "alpha", "alpha_t"]].to_dict("records"),
    }
