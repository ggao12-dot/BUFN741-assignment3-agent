from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.sandwich_covariance import cov_hac_simple
import statsmodels.api as sm


def summarize_lambdas(monthly: pd.DataFrame, hac_lags: int = 6) -> pd.DataFrame:
    rows = []
    columns = [c for c in monthly if c.startswith("lambda_")]
    for col in columns:
        values = monthly[col].dropna().to_numpy(float)
        if not len(values):
            continue
        mean, se = values.mean(), values.std(ddof=1)/np.sqrt(len(values))
        t = mean/se
        fit = sm.OLS(values, np.ones((len(values), 1))).fit()
        hse = np.sqrt(cov_hac_simple(fit, nlags=min(hac_lags, len(values)-1))[0, 0])
        df = len(values)-1
        rows.append({"universe": monthly.universe.iloc[0], "sample": monthly["sample"].iloc[0],
            "specification": int(monthly.specification.iloc[0]), "coefficient": col.removeprefix("lambda_"),
            "mean_lambda": mean, "fm_standard_error": se, "fm_t_stat": t,
            "fm_p_value": 2*stats.t.sf(abs(t), df), "hac_standard_error": hse,
            "hac_t_stat": mean/hse, "hac_p_value": 2*stats.t.sf(abs(mean/hse), df),
            "hac_lags": min(hac_lags, len(values)-1), "T": len(values)})
    return pd.DataFrame(rows)
