from __future__ import annotations

import numpy as np
from scipy import stats


def grs_test(alphas: np.ndarray, residuals: np.ndarray, factor_returns: np.ndarray, condition_limit: float = 1e12) -> tuple[dict, dict]:
    """Compute the finite-sample GRS statistic with strict validity checks.

    The standard ``T/N * (T-N-K)/(T-K-1)`` representation uses the OLS
    residual covariance divided by ``T-K-1``.  Factor covariance uses the
    population (1/T) convention appearing in the mean-factor adjustment.
    """
    alphas = np.asarray(alphas, float).reshape(-1)
    residuals, factor_returns = np.asarray(residuals, float), np.asarray(factor_returns, float)
    T, N = residuals.shape
    if factor_returns.shape[0] != T:
        raise ValueError("Factor and residual observations differ")
    K = factor_returns.shape[1]
    if T <= N+K:
        raise ValueError(f"GRS requires T>N+K; got {T}, {N}, {K}")
    sigma_e = residuals.T @ residuals / (T-K-1)
    centered = factor_returns-factor_returns.mean(axis=0)
    sigma_f = centered.T @ centered / T
    if np.linalg.matrix_rank(sigma_e) < N or np.linalg.cond(sigma_e) > condition_limit:
        raise ValueError("Residual covariance is singular or ill-conditioned")
    if np.linalg.matrix_rank(sigma_f) < K or np.linalg.cond(sigma_f) > condition_limit:
        raise ValueError("Factor covariance is singular or ill-conditioned")
    numerator = float(alphas @ np.linalg.solve(sigma_e, alphas))
    fmean = factor_returns.mean(axis=0)
    denominator = 1.0 + float(fmean @ np.linalg.solve(sigma_f, fmean))
    value = (T/N) * ((T-N-K)/(T-K-1)) * numerator/denominator
    result = {"N": N, "K": K, "T": T, "grs_F": value, "df1": N, "df2": T-N-K,
        "p_value": float(stats.f.sf(value, N, T-N-K))}
    intermediate = {"alpha_vector": alphas.tolist(), "residual_covariance": sigma_e.tolist(),
        "factor_mean": fmean.tolist(), "factor_covariance": sigma_f.tolist(),
        "residual_covariance_rank": int(np.linalg.matrix_rank(sigma_e)),
        "factor_covariance_rank": int(np.linalg.matrix_rank(sigma_f)),
        "residual_condition_number": float(np.linalg.cond(sigma_e)),
        "factor_condition_number": float(np.linalg.cond(sigma_f)),
        "alpha_quadratic_form": numerator, "factor_mean_adjustment": denominator}
    return result, intermediate
