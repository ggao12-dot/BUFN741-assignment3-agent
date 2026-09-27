from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from src.utils.config import FACTOR_COLUMNS


def estimate_second_pass(first_pass: pd.DataFrame, assets: pd.DataFrame, factor_names: list[str], **keys) -> tuple[pd.DataFrame, pd.DataFrame]:
    means = assets.set_index("date").mean()
    betas = first_pass.set_index("asset")[[f"beta_{f}" for f in factor_names]]
    common = means.index.intersection(betas.index)
    y, x = means.loc[common], betas.loc[common]
    fit = sm.OLS(y, sm.add_constant(x, has_constant="add")).fit()
    mapping = {"const": "intercept", **{f"beta_{f}": f for f in factor_names}}
    coefficients = pd.DataFrame([{**keys, "coefficient": mapping[name], "estimate": fit.params[name],
        "standard_error": fit.bse[name], "t_stat": fit.tvalues[name], "p_value": fit.pvalues[name],
        "cross_sectional_R2": fit.rsquared, "n_assets": len(y)} for name in fit.params.index])
    prediction = fit.predict(sm.add_constant(x, has_constant="add"))
    errors = pd.DataFrame({**{k: v for k, v in keys.items()}, "asset": common,
        "actual_mean_return": y.values, "predicted_mean_return": prediction.values})
    errors["pricing_error"] = errors.actual_mean_return-errors.predicted_mean_return
    errors["abs_pricing_error"] = errors.pricing_error.abs()
    return coefficients, errors

