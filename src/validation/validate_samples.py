from __future__ import annotations

import pandas as pd


def resolve_common_sample(frames: list[pd.DataFrame], requested_start: str, requested_end: str) -> dict:
    usable = []
    for frame in frames:
        values = frame.drop(columns="date")
        valid_rows = values.notna().any(axis=1)
        if not valid_rows.any():
            raise ValueError("A sample input has no usable observations")
        usable.append(frame.loc[valid_rows, "date"])
    starts = [dates.min() for dates in usable]
    ends = [dates.max() for dates in usable]
    start = max(pd.Period(requested_start, "M"), *starts)
    requested = min(ends) if requested_end == "latest_common" else pd.Period(requested_end, "M")
    end = min(requested, *ends)
    if start > end:
        raise ValueError("No common sample")
    return {"requested_start": requested_start, "requested_end": requested_end,
        "actual_start": str(start), "actual_end": str(end), "n_months": end.ordinal-start.ordinal+1}


def slice_sample(frame: pd.DataFrame, sample: dict) -> pd.DataFrame:
    start, end = pd.Period(sample["actual_start"], "M"), pd.Period(sample["actual_end"], "M")
    return frame.loc[frame.date.between(start, end)].copy()
