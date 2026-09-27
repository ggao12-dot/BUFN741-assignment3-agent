from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from src.utils.config import FACTOR_COLUMNS


def estimate_monthly_lambdas(aligned: pd.DataFrame, regressors: list[str], specification: int, sample: str) -> pd.DataFrame:
    rows = []
    beta_cols = [f"beta_{f}" for f in regressors]
    for date, group in aligned.groupby("return_date", sort=True):
        data = group[["excess_return", *beta_cols]].dropna()
        if len(data) <= len(regressors)+1:
            continue
        fit = sm.OLS(data.excess_return, sm.add_constant(data[beta_cols], has_constant="add")).fit()
        row = {"universe": group.universe.iloc[0], "sample": sample, "specification": specification,
            "beta_date": date-1, "return_month": date, "lambda_intercept": fit.params["const"],
            "cross_sectional_R2": fit.rsquared, "n_assets": len(data)}
        row.update({f"lambda_{f}": fit.params.get(f"beta_{f}", np.nan) for f in FACTOR_COLUMNS})
        rows.append(row)
    return pd.DataFrame(rows)

