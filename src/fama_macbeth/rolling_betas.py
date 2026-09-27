from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_rolling_betas(assets: pd.DataFrame, factors: pd.DataFrame, factor_names: list[str], window: int = 36, model: str = "") -> pd.DataFrame:
    """Estimate each asset on t-window+1..t; incomplete windows are omitted."""
    merged = assets.merge(factors[["date", *factor_names]], on="date", validate="one_to_one").sort_values("date")
    asset_names = list(assets.columns[1:])
    rows = []
    for end in range(window-1, len(merged)):
        block = merged.iloc[end-window+1:end+1]
        if block.date.iloc[-1].ordinal-block.date.iloc[0].ordinal != window-1:
            continue
        X0 = block[factor_names].to_numpy(float)
        for asset in asset_names:
            y = block[asset].to_numpy(float)
            valid = np.isfinite(y) & np.isfinite(X0).all(axis=1)
            if valid.sum() != window:
                continue
            X = np.column_stack([np.ones(window), X0])
            params = np.linalg.lstsq(X, y, rcond=None)[0]
            row = {"beta_date": block.date.iloc[-1], "asset": asset, "beta_source": model, "model": model,
                "window_start": block.date.iloc[0], "rolling_window_start": block.date.iloc[0],
                "rolling_window_end": block.date.iloc[-1], "window_n": window}
            row.update({f"beta_{f}": params[j+1] for j, f in enumerate(factor_names)})
            rows.append(row)
    return pd.DataFrame(rows)
