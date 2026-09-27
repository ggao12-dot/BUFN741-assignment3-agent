from __future__ import annotations

import pandas as pd


def alpha_grids(results: pd.DataFrame, metadata: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = results.merge(metadata[["asset_id", "size_bucket", "characteristic_bucket"]],
                           left_on="portfolio", right_on="asset_id", validate="one_to_one")
    alpha = joined.pivot(index="size_bucket", columns="characteristic_bucket", values="alpha")
    tstat = joined.pivot(index="size_bucket", columns="characteristic_bucket", values="alpha_t")
    if alpha.shape != (5, 5) or tstat.shape != (5, 5):
        raise ValueError("Alpha diagnostics require a complete 5x5 grid")
    return alpha, tstat

