"""Presentation figures for the interim report, derived only from saved results."""
from __future__ import annotations

from pathlib import Path
import os
import tempfile
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "bufn741-matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.config import ROOT


OUT = ROOT / "results/figures/interim_report"


def pricing_comparison(
    results_root: Path = ROOT / "results",
    processed_root: Path = ROOT / "data/processed",
    out: Path = OUT,
) -> Path:
    errors = pd.read_csv(results_root / "two_pass/pricing_errors.csv")
    metadata = pd.read_csv(processed_root / "grid_metadata.csv")
    data = errors.loc[(errors.family == "size_book_to_market") & errors.model.isin(["CAPM", "FF5"])].merge(
        metadata[["asset_id", "size_label", "characteristic_label"]], left_on="asset", right_on="asset_id")
    data["label"] = data.size_label + " / " + data.characteristic_label
    sample_labels = {"earlier": "July 1963–December 2010", "post_gfc": "January 2011–August 2026"}
    fig, axes = plt.subplots(2, 2, figsize=(13, 11), constrained_layout=True)
    for row, sample in enumerate(["earlier", "post_gfc"]):
        for col, model in enumerate(["CAPM", "FF5"]):
            ax = axes[row, col]
            use = data.loc[(data["sample"] == sample) & (data.model == model)].copy()
            x, y = use.predicted_mean_return*100, use.actual_mean_return*100
            lo, hi = min(x.min(), y.min()), max(x.max(), y.max())
            pad = max((hi-lo)*.08, .02)
            ax.scatter(x, y, s=32, color="#2166ac", alpha=.88)
            ax.plot([lo-pad, hi+pad], [lo-pad, hi+pad], "k--", lw=1)
            for _, point in use.nlargest(3, "abs_pricing_error").iterrows():
                ax.annotate(point.label, (point.predicted_mean_return*100, point.actual_mean_return*100),
                    xytext=(4, 4), textcoords="offset points", fontsize=7)
            ax.set_title(f"{model} — {sample_labels[sample]}")
            ax.set_xlabel("Predicted mean excess return (% per month)")
            ax.set_ylabel("Realized mean excess return (% per month)")
            ax.grid(alpha=.18)
    fig.suptitle("25 Size × Book-to-Market Portfolios: Realized versus Predicted Returns", fontsize=15)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "size_bm_pricing_four_panel.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


def lambda_comparison(
    results_root: Path = ROOT / "results",
    out: Path = OUT,
) -> Path:
    monthly = pd.read_csv(results_root / "fama_macbeth/monthly_lambdas/all.csv")
    monthly = monthly.loc[monthly.specification == 8].copy()
    monthly["return_month"] = pd.PeriodIndex(monthly.return_month, freq="M").to_timestamp()
    universe_labels = {"combined_univariate": "Combined univariate portfolios", "industries_49": "49 industries"}
    sample_labels = {"earlier": "Earlier", "post_gfc": "Post-GFC"}
    colors = {"MKT": "#2166ac", "SMB": "#f28e2b", "HML": "#59a14f", "RMW": "#d62728", "CMA": "#9467bd"}
    fig, axes = plt.subplots(2, 2, figsize=(15, 9), constrained_layout=True)
    for row, universe in enumerate(["combined_univariate", "industries_49"]):
        for col, sample in enumerate(["earlier", "post_gfc"]):
            ax = axes[row, col]; use = monthly.loc[(monthly.universe == universe) & (monthly["sample"] == sample)]
            for factor in colors:
                ax.plot(use.return_month, use[f"lambda_{factor}"]*100, lw=.65, color=colors[factor], label=factor)
            ax.axhline(0, color="black", lw=.7)
            ax.set_title(f"{universe_labels[universe]} — {sample_labels[sample]}")
            ax.set_ylabel("Factor price (% per month)"); ax.grid(alpha=.15)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.5, -.035), ncol=5, frameon=False)
    fig.suptitle("Fama–MacBeth Specification 8: Raw Monthly Factor Prices", fontsize=15, y=1.02)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "fm_spec8_lambdas_four_panel.png"
    fig.savefig(path, dpi=180, bbox_inches="tight"); plt.close(fig)
    return path


if __name__ == "__main__":
    pricing_comparison(); lambda_comparison()
