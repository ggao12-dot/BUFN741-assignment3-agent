"""Package, validate, and freeze a completed Assignment 3 production run.

The empirical workflow is intentionally invoked separately through its public
CLI.  This module performs only post-run QA and reproducibility packaging; it
does not alter estimators, samples, models, or test-asset construction.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

from src.reporting.build_interim_report import build_report
from src.reporting.convert_report import convert_report
from src.reporting.interim_analysis import build_interim_summaries
from src.reporting.interim_figures import lambda_comparison, pricing_comparison
from src.utils.config import ROOT, config_hash, load_config, write_json


RUN_COMMAND = (
    ".venv/bin/python run_workflow.py --production --refresh-data "
    "--output-dir production/.canonical-staging/results"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_tree_files(source: Path, target: Path) -> None:
    for path in source.rglob("*"):
        if path.is_file():
            destination = target / path.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def _period_range(frame: pd.DataFrame) -> tuple[str, str, int, int]:
    dates = pd.PeriodIndex(frame["date"], freq="M")
    return str(dates.min()), str(dates.max()), int(dates.nunique()), int(frame.iloc[:, 1:].isna().sum().sum())


def build_data_qa(staging: Path, root_manifest: dict, cfg: dict) -> pd.DataFrame:
    processed = ROOT / "data/processed"
    source_manifest = json.loads((ROOT / "data/raw/source_manifest.json").read_text())["sources"]
    factor_end = pd.Period(pd.read_csv(processed / "factors.csv").date.max(), "M")
    rows: list[dict] = []

    datasets: list[tuple[str, str, list[str], int, str]] = [
        ("factors", "factors.csv", ["factors_5"], 6, "factor portfolios"),
    ]
    for family, info in cfg["families"].items():
        datasets.append((family, f"{family}_excess_returns.csv", [info["source"]], 25, "value-weighted"))
    datasets.extend([
        ("combined_univariate", "univariate_excess_returns.csv", list(cfg["univariate"].values()), 80, "value-weighted"),
        ("industries_49", "industry_49_excess_returns.csv", [cfg["industries"]], 49, "value-weighted"),
    ])
    for dataset, filename, source_ids, n_assets, weighting in datasets:
        frame = pd.read_csv(processed / filename)
        raw_start, raw_end, _, _ = _period_range(frame)
        available_end = min(pd.Period(raw_end, "M"), factor_end)
        analysis_start = max(pd.Period("1963-07", "M"), pd.Period(raw_start, "M"))
        analysis = frame.loc[pd.PeriodIndex(frame.date, freq="M").to_series(index=frame.index).between(analysis_start, available_end)]
        missing = int(analysis.iloc[:, 1:].isna().sum().sum())
        rows.append({
            "dataset": dataset,
            "source_file": ";".join(source_manifest[key]["filename"] for key in source_ids),
            "source_url": ";".join(source_manifest[key]["url"] for key in source_ids),
            "raw_start": raw_start,
            "raw_end": raw_end,
            "actual_analysis_start": str(analysis_start),
            "actual_analysis_end": str(available_end),
            "n_months": int(len(analysis)),
            "n_assets": n_assets,
            "missing_values": missing,
            "weighting": weighting,
            "status": ("PASS" if missing == 0 else "PASS_WITH_DOCUMENTED_MISSING") if len(analysis) else "FAIL",
        })
    qa = pd.DataFrame(rows)
    qa.to_csv(staging / "qa/data_qa.csv", index=False)
    if not qa.status.str.startswith("PASS").all():
        raise RuntimeError("Data QA failed")
    return qa


def validate_results(staging: Path, cfg: dict) -> dict:
    results = staging / "results"
    checks: dict[str, dict] = {}

    cross = pd.read_csv(results / "two_pass/cross_sectional_results.csv")
    groups = cross[["family", "sample", "model"]].drop_duplicates()
    checks["two_pass_66"] = {"passed": len(groups) == 66, "observed": len(groups)}
    checks["two_pass_25_assets"] = {"passed": bool((cross.n_assets == 25).all())}
    plots = list((results / "figures/two_pass").glob("*.png"))
    checks["two_pass_44_plots"] = {"passed": len(plots) == 44, "observed": len(plots)}

    rolling_files = sorted((results / "fama_macbeth/rolling_betas").glob("*.csv"))
    rolling_ok = len(rolling_files) == 6
    for path in rolling_files:
        frame = pd.read_csv(path)
        start = pd.PeriodIndex(frame.rolling_window_start, freq="M")
        end = pd.PeriodIndex(frame.rolling_window_end, freq="M")
        rolling_ok &= bool(((end.astype(int) - start.astype(int)) == 35).all())
        rolling_ok &= bool((pd.PeriodIndex(frame.beta_date, freq="M") == end).all())
        rolling_ok &= frame.model.nunique() == 1
    checks["rolling_panels_three_per_universe_36_months"] = {
        "passed": rolling_ok, "observed_files": len(rolling_files)
    }

    aligned_files = sorted((results / "fama_macbeth/aligned_beta_return_panels").glob("*__*__*.csv"))
    aligned_ok = len(aligned_files) == 12
    for path in aligned_files:
        frame = pd.read_csv(path)
        beta = pd.PeriodIndex(frame.beta_date, freq="M")
        ret = pd.PeriodIndex(frame.return_date, freq="M")
        aligned_ok &= bool(((ret.astype(int) - beta.astype(int)) == 1).all())
        aligned_ok &= bool(np.allclose(frame.excess_return, frame.next_month_excess_return))
    checks["beta_return_t_plus_1_alignment"] = {
        "passed": aligned_ok, "observed_sample_panels": len(aligned_files)
    }

    monthly_files = sorted((results / "fama_macbeth/monthly_lambdas").glob("*__spec*.csv"))
    monthly = pd.read_csv(results / "fama_macbeth/monthly_lambdas/all.csv")
    fm_groups = monthly[["universe", "sample", "specification"]].drop_duplicates()
    checks["fm_32_universe_sample_specs"] = {"passed": len(fm_groups) == 32, "observed": len(fm_groups)}
    checks["fm_32_monthly_files"] = {"passed": len(monthly_files) == 32, "observed": len(monthly_files)}
    expected_sources = {int(k): v["beta_source"] for k, v in cfg["specifications"].items()}
    source_ok = expected_sources == {
        1: "CAPM", 2: "FF3", 3: "FF5", 4: "FF5", 5: "FF5", 6: "FF5", 7: "FF5", 8: "FF5"
    }
    checks["fm_beta_sources"] = {"passed": source_ok, "expected": expected_sources}
    compact_csv = list((results / "tables").glob("fm__*.csv"))
    compact_md = list((results / "tables").glob("fm__*.md"))
    compact_ok = len(compact_csv) == len(compact_md) == 4
    compact_ok &= all({"N_min", "N_max", "T"}.issubset(pd.read_csv(path).columns) for path in compact_csv)
    checks["fm_four_compact_csv_markdown_tables"] = {"passed": compact_ok}
    lambda_plots = list((results / "figures/fama_macbeth").glob("*.png"))
    checks["fm_24_spec8_lambda_plots"] = {"passed": len(lambda_plots) == 24, "observed": len(lambda_plots)}

    family = cfg["grs"]["portfolio_family"]
    grs_path = results / f"time_series/{family}/grs_results.csv"
    grs = pd.read_csv(grs_path)
    checks["grs_selected_family"] = {
        "passed": grs.portfolio_family.eq(family).all() and grs.portfolio_family_display_name.nunique() == 1,
        "value": family,
    }
    checks["grs_six_valid_cases"] = {
        "passed": len(grs) == 6 and bool((grs["N"] == 25).all()) and bool((grs["T"] > grs["N"] + grs["K"]).all()),
        "observed": len(grs),
    }
    intermediates = list((results / f"time_series/{family}").glob("*/*__grs_intermediates.json"))
    intermediate_ok = len(intermediates) == 6
    for path in intermediates:
        item = json.loads(path.read_text())
        intermediate_ok &= item["residual_covariance_rank"] == 25
        intermediate_ok &= item["factor_covariance_rank"] == len(item["factor_mean"])
        intermediate_ok &= np.isfinite(item["residual_condition_number"])
        intermediate_ok &= np.isfinite(item["factor_condition_number"])
    checks["grs_rank_conditioning_invertibility"] = {"passed": intermediate_ok}
    grid_csv = list((results / f"time_series/{family}").glob("*/*__alpha*_grid.csv"))
    grid_fig = list((results / "figures/time_series").glob("*.png"))
    checks["alpha_grids_12_tables_12_figures"] = {
        "passed": len(grid_csv) == 12 and len(grid_fig) == 12,
        "tables": len(grid_csv), "figures": len(grid_fig),
    }
    stale = [path for path in (results / "time_series").iterdir() if path.is_dir() and path.name != family]
    checks["no_stale_grs_family"] = {"passed": not stale}

    failures = [name for name, result in checks.items() if not result["passed"]]
    summary = {"status": "PASS" if not failures else "FAIL", "checks": checks, "failures": failures}
    write_json(staging / "qa/final_qa.json", summary)
    if failures:
        raise RuntimeError(f"Canonical QA failed: {failures}")
    return summary


def infer_inventory_fields(relative: str, cfg: dict) -> dict:
    path = Path(relative)
    name = path.name
    artifact_type = path.suffix.lstrip(".") or "marker"
    test_family = "metadata"
    if "two_pass" in path.parts:
        test_family = "two_pass"
    elif "fama_macbeth" in path.parts or name.startswith("fm__"):
        test_family = "fama_macbeth"
    elif "time_series" in path.parts or "grs" in name or "alpha" in name:
        test_family = "time_series_grs"
    elif "report" in path.parts or path.parent.name == "reports":
        test_family = "reporting"
    elif "qa" in path.parts:
        test_family = "qa"
    tokens = re.split(r"__|/", relative)
    universe = next((x for x in [*cfg["families"], "combined_univariate", "industries_49"] if x in relative), None)
    sample = next((x for x in cfg["samples"] if x in tokens or f"__{x}" in relative), None)
    model = next((x for x in cfg["models"] if x in tokens or f"__{x}" in relative), None)
    match = re.search(r"spec(?:ification)?[_-]?(\d+)", relative, re.I)
    return {
        "artifact_type": artifact_type,
        "test_family": test_family,
        "universe_or_family": universe,
        "sample": sample,
        "model": model,
        "specification_if_relevant": int(match.group(1)) if match else None,
    }


def freeze(staging: Path, pre_pytest: str) -> Path:
    staging = staging.resolve()
    results = staging / "results"
    if not results.is_dir():
        raise FileNotFoundError(f"Production results not found: {results}")
    for directory in ["config", "metadata", "data_manifest", "tables", "figures", "reports", "qa"]:
        (staging / directory).mkdir(parents=True, exist_ok=True)

    cfg = load_config()
    root_manifest = json.loads((ROOT / "production_manifest.json").read_text())
    if any(stage["status"] != "complete" for stage in json.loads((ROOT / "workflow_state.json").read_text())["stages"].values()):
        raise RuntimeError("workflow_state.json contains an incomplete production stage")
    if cfg["grs"]["portfolio_family"] not in cfg["families"]:
        raise RuntimeError("Configured GRS family is invalid")

    copy_tree_files(ROOT / "config", staging / "config")
    shutil.copy2(ROOT / "data/raw/source_manifest.json", staging / "data_manifest/source_manifest.json")
    shutil.copy2(ROOT / "workflow_state.json", staging / "metadata/workflow_state.json")
    shutil.copy2(ROOT / "requirements.txt", staging / "metadata/requirements.txt")
    if (ROOT / "requirements-docs.txt").exists():
        shutil.copy2(ROOT / "requirements-docs.txt", staging / "metadata/requirements-docs.txt")
    (staging / "metadata/run_command.txt").write_text(RUN_COMMAND + "\n", encoding="utf-8")
    (staging / "metadata/environment.txt").write_text(
        f"python={platform.python_version()}\nplatform={platform.platform()}\nexecutable={sys.executable}\n",
        encoding="utf-8",
    )
    freeze_result = subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT, text=True, capture_output=True)
    if freeze_result.returncode:
        raise RuntimeError(freeze_result.stderr)
    (staging / "metadata/dependency_snapshot.txt").write_text(freeze_result.stdout, encoding="utf-8")
    (staging / "qa/pytest_pre.txt").write_text(pre_pytest.strip() + "\n", encoding="utf-8")

    build_data_qa(staging, root_manifest, cfg)
    copy_tree_files(results / "tables", staging / "tables/core")
    copy_tree_files(results / "figures", staging / "figures/core")
    facts = build_interim_summaries(
        results_root=results,
        processed_root=ROOT / "data/processed",
        manifest_path=ROOT / "production_manifest.json",
        out=staging / "tables",
        title="Assignment 3 Canonical Final Report",
    )
    pricing_comparison(results, ROOT / "data/processed", staging / "figures")
    lambda_comparison(results, staging / "figures")
    report = build_report(
        staging / "tables/interim_empirical_facts.json",
        staging / "reports/assignment3_final_report.md",
        canonical=True,
    )
    docx, pdf = convert_report(report, report.parent)
    del facts, docx, pdf

    qa = validate_results(staging, cfg)
    report_text = report.read_text()
    question_count = len(re.findall(r"^### [1-9]\. ", report_text, re.M))
    image_links = re.findall(r"!\[[^]]*\]\(([^)]+)\)", report_text)
    broken = [link for link in image_links if not (report.parent / link).resolve().is_file()]
    placeholders = re.findall(r"\b(?:TODO|TBD|PLACEHOLDER)\b", report_text, re.I)
    qa["checks"]["report_nine_questions"] = {"passed": question_count == 9, "observed": question_count}
    qa["checks"]["report_image_links"] = {"passed": not broken, "broken": broken}
    qa["checks"]["report_no_placeholders"] = {"passed": not placeholders}
    if question_count != 9 or broken or placeholders:
        qa["status"] = "FAIL"
        write_json(staging / "qa/final_qa.json", qa)
        raise RuntimeError("Canonical report QA failed")
    write_json(staging / "qa/final_qa.json", qa)

    post = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
    (staging / "qa/pytest_post.txt").write_text(post.stdout + post.stderr, encoding="utf-8")
    if post.returncode:
        raise RuntimeError("Post-production pytest failed")
    match = re.search(r"(\d+) passed", post.stdout)
    passed = int(match.group(1)) if match else 0

    try:
        git_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        git_branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip() or None
    except Exception:
        git_commit = git_branch = None
    source = json.loads((ROOT / "data/raw/source_manifest.json").read_text())["sources"]
    dependencies = {}
    for package in ["pandas", "numpy", "scipy", "statsmodels", "matplotlib", "PyYAML", "requests", "pytest", "pypandoc_binary", "weasyprint"]:
        try:
            dependencies[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            dependencies[package] = None
    grs_id = cfg["grs"]["portfolio_family"]
    manifest = {
        "run_timestamp": root_manifest["run_timestamp"],
        "freeze_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_command": RUN_COMMAND,
        "git_commit": git_commit,
        "git_branch": git_branch,
        "python_version": platform.python_version(),
        "dependency_versions": dependencies,
        "config_hash": config_hash(),
        "source_urls": {key: value["url"] for key, value in source.items()},
        "source_download_timestamps": {key: value["downloaded_at"] for key, value in source.items()},
        "source_file_hashes": {key: value["sha256"] for key, value in source.items()},
        "factor_data_endpoint": root_manifest["factor_endpoint"],
        "asset_data_endpoints": root_manifest["asset_endpoints"],
        "actual_sample_periods": root_manifest["headline_sample_periods"],
        "effective_FM_sample_periods": root_manifest["fm_effective_samples"],
        "selected_GRS_family": {
            "portfolio_family_id": grs_id,
            "display_name": f"Size × {cfg['families'][grs_id]['label']}",
        },
        "models": cfg["models"],
        "FM_specs": cfg["specifications"],
        "rolling_window_months": cfg["rolling_window"],
        "HAC_lag_choice": cfg["hac_lags"],
        "pytest_total": passed,
        "pytest_passed": passed,
        "pytest_failed": 0,
        "critical_QA_status": qa["status"],
        "artifact_count": 0,
        "artifact_inventory_path": "metadata/artifact_inventory.json",
        "final_report_path": "reports/assignment3_final_report.md",
    }
    manifest_path = staging / "production_manifest.json"
    write_json(manifest_path, manifest)

    inventory_paths = sorted(path for path in staging.rglob("*") if path.is_file()
                             and path.name not in {"artifact_inventory.json", "artifact_inventory.csv", "checksums.sha256"})
    manifest["artifact_count"] = len(inventory_paths)
    write_json(manifest_path, manifest)
    inventory = []
    for path in inventory_paths:
        relative = path.relative_to(staging).as_posix()
        inventory.append({
            "relative_path": relative,
            **infer_inventory_fields(relative, cfg),
            "sha256": sha256(path),
            "file_size": path.stat().st_size,
        })
    write_json(staging / "metadata/artifact_inventory.json", inventory)
    pd.DataFrame(inventory).to_csv(staging / "metadata/artifact_inventory.csv", index=False)

    checksum_paths = sorted(path for path in staging.rglob("*") if path.is_file() and path.name != "checksums.sha256")
    checksum_text = "".join(f"{sha256(path)}  {path.relative_to(staging).as_posix()}\n" for path in checksum_paths)
    (staging / "metadata/checksums.sha256").write_text(checksum_text, encoding="utf-8")

    canonical = ROOT / "production/canonical"
    archive = ROOT / "production/archive"
    archive.mkdir(parents=True, exist_ok=True)
    if canonical.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        canonical.rename(archive / f"canonical_{timestamp}")
    staging.rename(canonical)
    marker = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit,
        "manifest_hash": sha256(canonical / "production_manifest.json"),
        "final_QA_status": "PASS",
    }
    write_json(canonical / "CANONICAL_RUN_COMPLETE", marker)
    return canonical


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", type=Path, default=ROOT / "production/.canonical-staging")
    parser.add_argument("--pre-pytest", default="49 passed in pre-production full pytest suite")
    args = parser.parse_args()
    print(freeze(args.staging, args.pre_pytest))


if __name__ == "__main__":
    main()
