from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from src.utils.config import FACTOR_COLUMNS


def portfolio_regressions(assets: pd.DataFrame, factors: pd.DataFrame, factor_names: list[str], **keys) -> tuple[pd.DataFrame, np.ndarray, pd.DataFrame]:
    merged = assets.merge(factors[["date", *factor_names]], on="date", validate="one_to_one").dropna()
    X = sm.add_constant(merged[factor_names], has_constant="add")
    rows, residuals = [], []
    for asset in assets.columns[1:]:
        fit = sm.OLS(merged[asset], X).fit()
        row = {**keys, "portfolio": asset, "alpha": fit.params["const"], "alpha_se": fit.bse["const"],
            "alpha_t": fit.tvalues["const"], "alpha_p": fit.pvalues["const"], "R2": fit.rsquared,
            "adj_R2": fit.rsquared_adj, "n_obs": int(fit.nobs)}
        for factor in FACTOR_COLUMNS:
            row[f"beta_{factor}"] = fit.params.get(factor, np.nan)
            row[f"beta_{factor}_t"] = fit.tvalues.get(factor, np.nan)
        rows.append(row)
        residuals.append(fit.resid.to_numpy())
    return pd.DataFrame(rows), np.column_stack(residuals), merged[["date", *factor_names]]

