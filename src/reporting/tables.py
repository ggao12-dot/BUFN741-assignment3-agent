from __future__ import annotations

from pathlib import Path
import pandas as pd


def fm_compact_table(summary: pd.DataFrame, path: Path, monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    view = summary.copy()
    view["display"] = view.apply(lambda r: f"{r.mean_lambda:.4f} ({r.fm_t_stat:.2f})", axis=1)
    table = view.pivot(index="specification", columns="coefficient", values="display")
    if monthly is not None:
        dimensions = monthly.groupby("specification").agg(
            N_min=("n_assets", "min"), N_max=("n_assets", "max"), T=("return_month", "nunique"))
        table = table.join(dimensions)
    path.parent.mkdir(parents=True, exist_ok=True); table.to_csv(path)
    markdown = path.with_suffix(".md")
    rendered = table.reset_index().fillna("")
    headers = [str(column) for column in rendered.columns]
    rows = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"]*len(headers)) + "|"]
    rows.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rendered.itertuples(index=False, name=None))
    markdown.write_text("\n".join(rows)+"\n", encoding="utf-8")
    return table
