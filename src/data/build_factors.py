from __future__ import annotations

from pathlib import Path
import pandas as pd
from src.data.parse_french import select_value_weighted, percent_to_decimal


def build_factors(raw_dir: Path) -> pd.DataFrame:
    ff3 = percent_to_decimal(select_value_weighted(raw_dir / "F-F_Research_Data_Factors_CSV.zip"))
    ff5 = percent_to_decimal(select_value_weighted(raw_dir / "F-F_Research_Data_5_Factors_2x3_CSV.zip"))
    ff3 = ff3.rename(columns={"Mkt-RF": "MKT", "Mkt-Rf": "MKT"})
    ff5 = ff5.rename(columns={"Mkt-RF": "MKT", "Mkt-Rf": "MKT"})
    needed = ["date", "MKT", "SMB", "HML", "RMW", "CMA", "RF"]
    out = ff5[[c for c in needed if c in ff5]].copy()
    # FF5 is canonical from July 1963; RF and all five factors come from one file.
    if list(out.columns) != needed:
        raise ValueError(f"Canonical factor columns missing: {set(needed)-set(out)}")
    if out.date.duplicated().any():
        raise ValueError("Duplicate factor dates")
    out.attrs["return_units"] = "decimal"
    return out

