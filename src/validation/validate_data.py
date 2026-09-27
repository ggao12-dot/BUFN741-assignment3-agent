from __future__ import annotations

import numpy as np
import pandas as pd


def validate_monthly(frame: pd.DataFrame, expected_assets: int | None = None, excess: bool | None = None) -> None:
    if "date" not in frame or not isinstance(frame["date"].dtype, pd.PeriodDtype):
        raise ValueError("date must be a monthly Period column")
    if frame.date.duplicated().any() or not frame.date.is_monotonic_increasing:
        raise ValueError("dates must be unique and sorted")
    ordinals = frame.date.map(lambda value: value.ordinal).to_numpy()
    if len(ordinals) > 1 and not np.all(np.diff(ordinals) == 1):
        raise ValueError("monthly dates must be contiguous")
    if expected_assets is not None and len(frame.columns) - 1 != expected_assets:
        raise ValueError(f"Expected {expected_assets} assets")
    if frame.attrs.get("return_units") != "decimal":
        raise ValueError("returns must be decimal")
    if excess is not None and bool(frame.attrs.get("excess_returns")) != excess:
        raise ValueError("excess-return status mismatch")
    values = frame.drop(columns="date").to_numpy(float)
    missing_columns = frame.drop(columns="date").columns[np.isnan(values).all(axis=0)].tolist()
    if missing_columns:
        raise ValueError(f"Columns have no usable observations: {missing_columns}")
    if np.nanquantile(np.abs(values), .999) > 3:
        raise ValueError("implausible decimal return magnitude")


def validate_grid_metadata(metadata: pd.DataFrame, family: str) -> None:
    part = metadata[metadata.family == family]
    if len(part) != 25 or part.asset_id.nunique() != 25:
        raise ValueError(f"{family} must have 25 unique assets")
    expected = {(i, j) for i in range(1, 6) for j in range(1, 6)}
    actual = set(zip(part.size_bucket, part.characteristic_bucket))
    if actual != expected:
        raise ValueError(f"{family} has incomplete grid metadata")
