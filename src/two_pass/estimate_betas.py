from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from src.utils.config import FACTOR_COLUMNS


def estimate_first_pass(assets: pd.DataFrame, factors: pd.DataFrame, factor_names: list[str], **keys) -> pd.DataFrame:
    merged = assets.merge(factors[["date", *factor_names]], on="date", validate="one_to_one")
    rows = []
    for asset in assets.columns[1:]:
        data = merged[[asset, *factor_names]].dropna()
        fit = sm.OLS(data[asset], sm.add_constant(data[factor_names], has_constant="add")).fit()
        row = {**keys, "asset": asset, "alpha": fit.params["const"], "alpha_se": fit.bse["const"],
            "alpha_t": fit.tvalues["const"], "R2": fit.rsquared, "adj_R2": fit.rsquared_adj, "n_obs": int(fit.nobs)}
        row.update({f"beta_{f}": fit.params.get(f, np.nan) for f in FACTOR_COLUMNS})
        rows.append(row)
    return pd.DataFrame(rows)

