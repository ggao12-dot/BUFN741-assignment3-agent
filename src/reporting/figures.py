from __future__ import annotations

from pathlib import Path
import os
import tempfile
_mpl_cache = Path(tempfile.gettempdir()) / "bufn741-matplotlib"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def pricing_plot(errors: pd.DataFrame, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    x, y = errors.predicted_mean_return*100, errors.actual_mean_return*100
    bounds = [min(x.min(), y.min()), max(x.max(), y.max())]
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    ax.scatter(x, y, s=25)
    ax.plot(bounds, bounds, "k--", lw=1)
    for _, row in errors.nlargest(3, "abs_pricing_error").iterrows():
        size = row.asset.split("__")[-2].removeprefix("s")
        characteristic = row.asset.split("__")[-1].removeprefix("c")
        ax.annotate(f"S{size}/C{characteristic}", (row.predicted_mean_return*100, row.actual_mean_return*100), fontsize=7)
    ax.set(xlabel="Predicted mean excess return (% per month)", ylabel="Realized mean excess return (% per month)", title=title)
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def lambda_plot(monthly: pd.DataFrame, path: Path, factors: list[str] | None = None) -> None:
    factors = factors or ["MKT", "SMB", "HML", "RMW", "CMA"]
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    dates = monthly.return_month.dt.to_timestamp()
    for factor in factors:
        ax.plot(dates, monthly[f"lambda_{factor}"], lw=.7, label=factor)
    ax.axhline(0, color="black", lw=.7); ax.legend(ncol=len(factors)); ax.set_ylabel("Monthly factor price")
    fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)


def grid_plot(grid: pd.DataFrame, path: Path, title: str, column_label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(6.2, 5))
    image = ax.imshow(grid.to_numpy(), cmap="RdBu_r", aspect="auto")
    ax.set_xticks(range(5), [f"Low {column_label}", "2", "3", "4", f"High {column_label}"], rotation=20)
    ax.set_yticks(range(5), ["Small", "2", "3", "4", "Big"])
    ax.set(xlabel=column_label, ylabel="Size", title=title)
    for i in range(5):
        for j in range(5): ax.text(j, i, f"{grid.iloc[i,j]:.3f}", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax); fig.tight_layout(); fig.savefig(path, dpi=160); plt.close(fig)
