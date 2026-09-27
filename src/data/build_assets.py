from __future__ import annotations

from pathlib import Path
import pandas as pd
from src.data.metadata import SOURCE_FILES
from src.data.parse_french import select_value_weighted, percent_to_decimal, finest_partition


def add_excess_returns(returns: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    if returns.attrs.get("excess_returns"):
        raise ValueError("RF has already been subtracted")
    if returns.attrs.get("return_units") != "decimal" or factors.attrs.get("return_units") != "decimal":
        raise ValueError("Returns and factors must both use decimal units")
    joined = returns.merge(factors[["date", "RF"]], on="date", validate="one_to_one")
    assets = [c for c in returns if c != "date"]
    joined[assets] = joined[assets].sub(joined["RF"], axis=0)
    out = joined.drop(columns="RF")
    out.attrs.update(return_units="decimal", excess_returns=True)
    return out


def _grid_metadata(family: str, columns: list[str], source: str, label: str) -> pd.DataFrame:
    rows = []
    for position, col in enumerate(columns):
        size, characteristic = divmod(position, 5)
        rows.append({"asset_id": f"{family}__s{size+1}__c{characteristic+1}", "original_label": col,
            "family": family, "size_bucket": size+1, "characteristic_bucket": characteristic+1,
            "size_label": ["Small", "2", "3", "4", "Big"][size],
            "characteristic_label": [f"Low {label}", "2", "3", "4", f"High {label}"][characteristic],
            "source_file": SOURCE_FILES[source], "weighting": "value"})
    return pd.DataFrame(rows)


def build_5x5(raw_dir: Path, factors: pd.DataFrame, families: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    panels, metadata = {}, []
    for family, info in families.items():
        source = info["source"]
        returns = select_value_weighted(raw_dir / SOURCE_FILES[source])
        # The library's file titled "25 Portfolios ... Net Share Issues" also
        # publishes negative-issuance and zero-issuance side portfolios for each
        # size group.  The requested 5x5 grid is the five positive-NI buckets.
        if source == "portfolios_25_size_ni":
            keep = [c for c in returns.columns[1:] if "NegNI" not in c and "ZeroNI" not in c]
            returns = returns[["date", *keep]]
        if len(returns.columns) - 1 != 25:
            raise ValueError(f"{SOURCE_FILES[source]}: expected a 5x5 grid, got {len(returns.columns)-1} assets")
        returns = percent_to_decimal(returns)
        meta = _grid_metadata(family, list(returns.columns[1:]), source, info["short_label"])
        returns.columns = ["date", *meta.asset_id]
        panels[family] = add_excess_returns(returns, factors)
        metadata.append(meta)
    return panels, pd.concat(metadata, ignore_index=True)


def build_univariate(raw_dir: Path, factors: pd.DataFrame, definitions: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panels, metadata, audit = [], [], []
    for characteristic, source in definitions.items():
        raw = percent_to_decimal(select_value_weighted(raw_dir / SOURCE_FILES[source]))
        selected = finest_partition(raw)
        n = len(selected.columns) - 1
        ids = [f"{characteristic}__p{i+1:02d}" for i in range(n)]
        labels = list(selected.columns[1:])
        selected.columns = ["date", *ids]
        panels.append(selected.set_index("date"))
        metadata.extend({"asset_id": aid, "characteristic": characteristic, "portfolio_rank": i+1,
            "portfolio_label": labels[i], "partition_count": n, "source_file": SOURCE_FILES[source]} for i, aid in enumerate(ids))
        audit.append({"characteristic": characteristic, "source_dataset": SOURCE_FILES[source],
            "partition_used": n, "number_of_portfolios": n})
    combined = pd.concat(panels, axis=1, join="outer").reset_index()
    combined.attrs["return_units"] = "decimal"
    audit_df = pd.DataFrame(audit)
    audit_df["final_total_cross_sectional_assets"] = sum(audit_df.number_of_portfolios)
    return add_excess_returns(combined, factors), pd.DataFrame(metadata), audit_df


def build_industries(raw_dir: Path, factors: pd.DataFrame) -> pd.DataFrame:
    returns = percent_to_decimal(select_value_weighted(raw_dir / SOURCE_FILES["industries_49"], 49))
    return add_excess_returns(returns, factors)
