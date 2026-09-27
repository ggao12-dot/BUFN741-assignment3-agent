# BUFN741 Assignment 3 Asset-Pricing Harness

This repository is a configuration-driven research system for three complementary empirical tests: full-sample two-pass cross-sectional tests, predictive Fama–MacBeth regressions, and portfolio time-series regressions with Gibbons–Ross–Shanken joint-alpha tests.

## Data and design

The authoritative source is the [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html). The downloader caches the original ZIP archives in `data/raw/`, records URLs, timestamps and SHA-256 hashes, and selects the first monthly table in each file—the value-weighted return table. It supports eleven 5×5 Size × Characteristic families, eight combined univariate sorts using the finest available partition, and 49 industries.

French percentages are converted to decimal returns once. The canonical factor table is `date, MKT, SMB, HML, RMW, CMA, RF`, where MKT is already the market excess return. Asset excess returns are constructed centrally and tagged to prevent a second RF subtraction.

## Architecture

- `config/`: models, samples, universes, FM specifications, workflow settings.
- `src/data/`: verified download catalog, resilient monthly-block parser, processed factors/assets and metadata.
- `src/validation/`: units, cardinality, grid, date and common-sample invariants.
- `src/two_pass/`: full-period beta estimation, second-pass prices/errors and HML diagnostics.
- `src/fama_macbeth/`: exactly 36-observation rolling betas, auditable t-to-t+1 alignment, eight cross sections and inference.
- `src/time_series/`: portfolio regressions, strict GRS computation and 5×5 alpha diagnostics.
- `src/reporting/`: tables, traceable figures, structured interpretation facts and Markdown assembly.
- `run_workflow.py`: restart-visible, fail-fast orchestration.

## Installation and use

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
.venv/bin/python run_workflow.py
.venv/bin/python run_workflow.py --production
.venv/bin/python run_workflow.py --production --grs-family size_book_to_market
```

Use `--refresh-data` to replace cached ZIPs, `--skip-download` for an existing complete cache, and `--output-dir PATH` for an isolated result tree. A production run cannot disable GRS and runs pytest before emitting `production_manifest.json` and the final report.

The default GRS family is `size_momentum`; change `grs.portfolio_family` in `config/workflow.yaml` or use the CLI override. Any ID in `config/asset_universes.yaml` is valid.

## Outputs and audit trail

Raw archives and their manifest remain under `data/raw/`; canonical tables and metadata are under `data/processed/`. Machine-readable estimates, errors, rolling panels, aligned panels, lambdas, GRS intermediates, CSV tables and PNG figures are under `results/`. `results/interpretation_facts.json` is the only analytical input to `reports/assignment3_final_report.md`. `production_manifest.json` inventories artifacts, configurations, dependencies, hashes, endpoints, resolved periods and test results.

The post-audit interim empirical report can be reproduced without rerunning the estimators:

```bash
.venv/bin/python -m src.reporting.interim_analysis
.venv/bin/python -m src.reporting.interim_figures
.venv/bin/python -m src.reporting.build_interim_report
```

This writes report-ready structured summaries to `results/tables/interim_report/` and the labeled pre-canonical report to `reports/assignment3_empirical_results_report.md`.

Optional DOCX/PDF conversion uses the isolated document stack:

```bash
.venv/bin/python -m pip install -r requirements-docs.txt
.venv/bin/python -m src.reporting.convert_report reports/assignment3_empirical_results_report.md
```

## Econometric invariants

- All regressions include an intercept and use consistently aligned decimal excess returns.
- Test I betas use the complete selected period, never rolling windows.
- Rolling beta windows contain exactly t−35 through t; those betas explain t+1. Pre-2011 history is deliberately allowed for January 2011 predictions.
- FM spec 1 uses CAPM betas, spec 2 uses joint FF3 betas, and specs 3–8 reuse one full-FF5 beta panel.
- GRS requires `T > N + K`, full-rank and acceptably conditioned residual and factor covariance matrices; no pseudoinverse is used.

A **beta** is a portfolio's factor exposure, a **lambda** is the cross-sectional price of exposure, an **alpha** is a time-series intercept, and a **pricing error** is realized minus second-pass fitted mean return. Cross-sectional and time-series R² values are not interchangeable; FM t-statistics concern average monthly prices, while GRS tests all portfolio alphas jointly.

## Limitations

The 36-month beta window is intentionally fixed by the assignment and can be noisy or slow to reflect structural change. Two-pass standard errors do not apply an errors-in-variables correction. Results inherit source revisions and portfolio-construction choices. The report therefore preserves computed evidence without automatically declaring a factor redundant or naming a universally “best” model.
