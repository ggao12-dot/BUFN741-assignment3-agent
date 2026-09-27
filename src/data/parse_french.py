from __future__ import annotations

from io import StringIO
from pathlib import Path
import re
import zipfile
import numpy as np
import pandas as pd

MISSING_CODES = {-99.99, -999.0, -999.99}


def read_zip_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.lower().endswith((".csv", ".txt"))]
        if len(names) != 1:
            raise ValueError(f"Expected one data member in {path}, got {names}")
        return archive.read(names[0]).decode("utf-8-sig", errors="replace")


def _monthly_blocks(text: str) -> list[tuple[int, int]]:
    lines = text.splitlines()
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        if re.match(r"^\s*,", lines[i]) and i + 1 < len(lines) and re.match(r"^\s*\d{6}\s*,", lines[i + 1]):
            j = i + 1
            while j < len(lines) and re.match(r"^\s*\d{6}\s*,", lines[j]):
                j += 1
            blocks.append((i, j))
            i = j
        else:
            i += 1
    return blocks


def parse_monthly_tables(path: Path) -> list[pd.DataFrame]:
    """Return every monthly table in a French CSV ZIP, in file order."""
    text = read_zip_text(path)
    lines = text.splitlines()
    out = []
    for start, stop in _monthly_blocks(text):
        frame = pd.read_csv(StringIO("\n".join(lines[start:stop])), skipinitialspace=True)
        frame = frame.rename(columns={frame.columns[0]: "date"})
        frame["date"] = pd.PeriodIndex(frame["date"].astype(str).str.strip(), freq="M")
        frame.columns = [str(c).strip() for c in frame.columns]
        for col in frame.columns[1:]:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
            frame.loc[frame[col].isin(MISSING_CODES), col] = np.nan
        out.append(frame)
    if not out:
        raise ValueError(f"No monthly table found in {path}")
    return out


def select_value_weighted(path: Path, expected_assets: int | None = None) -> pd.DataFrame:
    """Select the monthly value-weighted table by its published heading.

    Factor files have no weighting heading; for those files the sole/first
    monthly table is returned.  Portfolio files that advertise weighting must
    contain an identifiable value-weighted table, preventing a future source
    reorder from silently selecting equal-weighted returns.
    """
    text = read_zip_text(path)
    lines = text.splitlines()
    blocks = _monthly_blocks(text)
    weighted_headings_present = any("weight" in line.lower() and "monthly" in line.lower() for line in lines)
    selected: tuple[int, int] | None = None
    previous_stop = 0
    for start, stop in blocks:
        context = " ".join(lines[max(previous_stop, start - 8):start]).lower()
        is_value = ("value weighted" in context or "value weight returns" in context) and "monthly" in context
        if is_value:
            selected = (start, stop)
            break
        previous_stop = stop
    if selected is None:
        if weighted_headings_present:
            raise ValueError(f"Could not identify monthly value-weighted table in {path}")
        selected = blocks[0]
    start, stop = selected
    frame = pd.read_csv(StringIO("\n".join(lines[start:stop])), skipinitialspace=True)
    frame = frame.rename(columns={frame.columns[0]: "date"})
    frame["date"] = pd.PeriodIndex(frame["date"].astype(str).str.strip(), freq="M")
    frame.columns = [str(c).strip() for c in frame.columns]
    for col in frame.columns[1:]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
        frame.loc[frame[col].isin(MISSING_CODES), col] = np.nan
    if expected_assets is not None and len(frame.columns) - 1 != expected_assets:
        raise ValueError(f"{path.name}: expected {expected_assets} assets, got {len(frame.columns)-1}")
    return frame


def percent_to_decimal(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    cols = [c for c in out if c != "date"]
    out[cols] = out[cols] / 100.0
    out.attrs["return_units"] = "decimal"
    return out


def finest_partition(frame: pd.DataFrame) -> pd.DataFrame:
    """Select deciles, then quintiles, terciles, or the widest coherent partition."""
    cols = list(frame.columns[1:])
    lower = [c.lower().strip() for c in cols]

    def block(start_markers: set[str], end_markers: set[str], n: int) -> list[str] | None:
        for i, label in enumerate(lower):
            if label in start_markers and i + n <= len(cols) and lower[i+n-1] in end_markers:
                return cols[i:i+n]
        return None

    choices = (
        block({"lo 10", "lo prior"}, {"hi 10", "hi prior"}, 10),
        block({"lo 20"}, {"hi 20"}, 5),
        block({"lo 30"}, {"hi 30"}, 3),
    )
    for choice in choices:
        if choice is not None:
            return frame[["date", *choice]]
    # A source may publish a single nonstandard partition. Exclude explicitly
    # named non-ranked side portfolios, then use the finest available block.
    ranked = [c for c in cols if c.lower().strip() not in {"< 0", "<= 0", "zero"}]
    if len(ranked) >= 2:
        return frame[["date", *ranked]]
    raise ValueError(f"No recognizable ranked partition in columns: {cols}")
