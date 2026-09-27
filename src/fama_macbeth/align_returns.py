from __future__ import annotations

import pandas as pd


def align_beta_return(betas: pd.DataFrame, assets: pd.DataFrame, universe: str) -> pd.DataFrame:
    long = assets.melt("date", var_name="asset", value_name="excess_return").rename(columns={"date": "return_date"})
    long["beta_date"] = long.return_date - 1
    out = betas.merge(long, on=["beta_date", "asset"], validate="one_to_one")
    if not ((out.return_date-out.beta_date).apply(lambda x: x.n) == 1).all():
        raise ValueError("Beta date must predict exactly t+1")
    out.insert(0, "universe", universe)
    return out

