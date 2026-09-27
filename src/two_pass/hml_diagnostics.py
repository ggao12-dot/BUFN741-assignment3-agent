from __future__ import annotations

import pandas as pd
from src.two_pass.cross_section import estimate_second_pass


def hml_diagnostic(first_pass_ff5: pd.DataFrame, assets: pd.DataFrame, **keys) -> dict:
    reduced, _ = estimate_second_pass(first_pass_ff5, assets, ["MKT", "SMB", "RMW", "CMA"], **keys)
    full, _ = estimate_second_pass(first_pass_ff5, assets, ["MKT", "SMB", "HML", "RMW", "CMA"], **keys)
    hml = full.loc[full.coefficient == "HML"].iloc[0]
    r0, r1 = reduced.cross_sectional_R2.iloc[0], full.cross_sectional_R2.iloc[0]
    return {**keys, "lambda_HML": hml.estimate, "HML_standard_error": hml.standard_error,
        "HML_t_stat": hml.t_stat, "HML_p_value": hml.p_value,
        "R2_without_HML": r0, "R2_with_HML": r1, "delta_R2": r1-r0}

