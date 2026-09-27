from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import logging
from pathlib import Path
import platform
import subprocess
import sys
import traceback
import pandas as pd

from src.data.download_french import download_all, validate_cache
from src.data.build_factors import build_factors
from src.data.build_assets import build_5x5, build_univariate, build_industries
from src.validation.validate_data import validate_monthly, validate_grid_metadata
from src.validation.validate_samples import resolve_common_sample, slice_sample
from src.two_pass.estimate_betas import estimate_first_pass
from src.two_pass.cross_section import estimate_second_pass
from src.two_pass.hml_diagnostics import hml_diagnostic
from src.fama_macbeth.rolling_betas import estimate_rolling_betas
from src.fama_macbeth.align_returns import align_beta_return
from src.fama_macbeth.monthly_cross_sections import estimate_monthly_lambdas
from src.fama_macbeth.inference import summarize_lambdas
from src.time_series.portfolio_regressions import portfolio_regressions
from src.time_series.grs_test import grs_test
from src.time_series.alpha_diagnostics import alpha_grids
from src.reporting.figures import pricing_plot, lambda_plot, grid_plot
from src.reporting.tables import fm_compact_table
from src.reporting.interpretation_facts import build_facts
from src.reporting.build_report import build_report
from src.utils.config import ROOT, config_hash, load_config, write_json

LOG = logging.getLogger("assignment3")


class Workflow:
    def __init__(self, output: Path, production: bool, grs_family: str | None, refresh: bool, skip_download: bool):
        self.cfg = load_config(); self.output = output; self.production = production
        self.raw = ROOT / "data" / "raw"; self.processed = ROOT / "data" / "processed"
        self.grs_family = grs_family or self.cfg["grs"]["portfolio_family"]
        if self.grs_family not in self.cfg["families"]:
            raise ValueError(f"Unknown GRS family: {self.grs_family}")
        if production and not self.cfg["grs"].get("enabled", True):
            raise ValueError("Production cannot disable GRS")
        self.refresh, self.skip_download = refresh, skip_download
        self.state_path = ROOT / "workflow_state.json"
        self.samples: dict[str, dict] = {}; self.artifacts: list[str] = []

    def display_path(self, path: Path) -> str:
        return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)

    def initialize_state(self) -> None:
        if not self.production:
            return
        stages = ["data_acquisition", "data_processing", "data_validation", "two_pass",
                  "fama_macbeth", "time_series_grs", "reporting", "final_qa"]
        write_json(self.state_path, {"production": True, "run_started_at": datetime.now(timezone.utc).isoformat(),
            "selected_grs_family": self.grs_family,
            "stages": {name: {"status": "pending", "timestamp": None, "detail": None} for name in stages}})

    def stage(self, name: str, status: str, detail: str | None = None) -> None:
        if not self.production: return
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"production": True, "stages": {}}
        state["stages"][name] = {"status": status, "timestamp": datetime.now(timezone.utc).isoformat(), "detail": detail}
        write_json(self.state_path, state)

    def save_csv(self, frame: pd.DataFrame, relative: str) -> Path:
        path = self.output / relative; path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False); self.artifacts.append(self.display_path(path)); return path

    def acquire_build_validate(self):
        self.stage("data_acquisition", "running")
        if not self.skip_download: self.source_manifest = download_all(self.raw, self.refresh)
        else: self.source_manifest = validate_cache(self.raw)
        self.stage("data_acquisition", "complete")
        self.stage("data_processing", "running")
        factors = build_factors(self.raw)
        panels, grid_meta = build_5x5(self.raw, factors, self.cfg["families"])
        univariate, uni_meta, uni_audit = build_univariate(self.raw, factors, self.cfg["univariate"])
        industries = build_industries(self.raw, factors)
        self.processed.mkdir(parents=True, exist_ok=True)
        factors.to_csv(self.processed / "factors.csv", index=False)
        grid_meta.to_csv(self.processed / "grid_metadata.csv", index=False)
        uni_meta.to_csv(self.processed / "univariate_metadata.csv", index=False)
        uni_audit.to_csv(self.processed / "univariate_partition_audit.csv", index=False)
        univariate.to_csv(self.processed / "univariate_excess_returns.csv", index=False)
        industries.to_csv(self.processed / "industry_49_excess_returns.csv", index=False)
        for family, panel in panels.items(): panel.to_csv(self.processed / f"{family}_excess_returns.csv", index=False)
        self.stage("data_processing", "complete")
        self.stage("data_validation", "running")
        validate_monthly(factors, excess=False)
        for family, panel in panels.items():
            validate_monthly(panel, 25, True); validate_grid_metadata(grid_meta, family)
        validate_monthly(industries, 49, True); validate_monthly(univariate, excess=True)
        self.stage("data_validation", "complete")
        return factors, panels, grid_meta, univariate, uni_audit, industries

    def resolve(self, factors, assets, sample_name):
        spec = self.cfg["samples"][sample_name]
        result = resolve_common_sample([factors, assets], spec["start"], spec["end"])
        self.samples[f"{sample_name}:{assets.columns[1]}"] = result
        return result

    def run_two_pass(self, factors, panels):
        self.stage("two_pass", "running")
        first_all=[]; second_all=[]; errors_all=[]; hml_all=[]
        for family, assets in panels.items():
            for sample_name in self.cfg["samples"]:
                resolved=self.resolve(factors, assets, sample_name)
                a, f=slice_sample(assets,resolved), slice_sample(factors,resolved)
                family_first={}
                for model, names in self.cfg["models"].items():
                    keys={"family":family,"sample":sample_name,"model":model}
                    first=estimate_first_pass(a,f,names,**keys); family_first[model]=first; first_all.append(first)
                    second, errors=estimate_second_pass(first,a,names,**keys); second_all.append(second); errors_all.append(errors)
                    if model in {"CAPM","FF5"}:
                        label=self.cfg["families"][family]["label"]
                        pricing_plot(errors,self.output/f"figures/two_pass/{family}__{sample_name}__{model}.png",
                            f"Size × {label} — {model} — {resolved['actual_start']} to {resolved['actual_end']}")
                hml_all.append(hml_diagnostic(family_first["FF5"],a,family=family,sample=sample_name))
        first=pd.concat(first_all,ignore_index=True); second=pd.concat(second_all,ignore_index=True)
        errors=pd.concat(errors_all,ignore_index=True); hml=pd.DataFrame(hml_all)
        self.save_csv(first,"two_pass/first_pass_betas.csv"); self.save_csv(second,"two_pass/cross_sectional_results.csv")
        self.save_csv(errors,"two_pass/pricing_errors.csv"); self.save_csv(hml,"two_pass/hml_diagnostics.csv")
        self.stage("two_pass", "complete"); return second, errors, hml

    def run_fm(self, factors, universes):
        self.stage("fama_macbeth", "running")
        all_monthly=[]; all_summary=[]; effective=[]
        for universe, assets in universes.items():
            rolling={}
            for model,names in self.cfg["models"].items():
                rolling[model]=estimate_rolling_betas(assets,factors,names,self.cfg["rolling_window"],model)
                self.save_csv(rolling[model],f"fama_macbeth/rolling_betas/{universe}__{model}.csv")
            aligned={model:align_beta_return(panel,assets,universe) for model,panel in rolling.items()}
            for model,panel in aligned.items(): self.save_csv(panel,f"fama_macbeth/aligned_beta_return_panels/{universe}__{model}.csv")
            for sample_name,sample_cfg in self.cfg["samples"].items():
                resolved=self.resolve(factors,assets,sample_name)
                lo,hi=pd.Period(resolved["actual_start"],"M"),pd.Period(resolved["actual_end"],"M")
                for model, panel in aligned.items():
                    sampled = panel.loc[panel.return_date.between(lo, hi)].copy()
                    sampled.insert(1, "sample", sample_name)
                    sampled["next_month_excess_return"] = sampled.excess_return
                    self.save_csv(sampled, f"fama_macbeth/aligned_beta_return_panels/{universe}__{sample_name}__{model}.csv")
                for spec,definition in self.cfg["specifications"].items():
                    source=definition["beta_source"]
                    use=aligned[source].loc[aligned[source].return_date.between(lo,hi)]
                    monthly=estimate_monthly_lambdas(use,definition["regressors"],spec,sample_name)
                    if monthly.empty: raise RuntimeError(f"No FM cross sections: {universe}/{sample_name}/spec{spec}")
                    self.save_csv(monthly, f"fama_macbeth/monthly_lambdas/{universe}__{sample_name}__spec{spec}.csv")
                    effective.append({"universe": universe, "sample": sample_name, "specification": spec,
                        "first_beta_date": str(monthly.beta_date.min()), "first_return_month": str(monthly.return_month.min()),
                        "last_return_month": str(monthly.return_month.max()), "T": int(monthly.return_month.nunique())})
                    all_monthly.append(monthly); all_summary.append(summarize_lambdas(monthly,self.cfg["hac_lags"]))
                    if spec==8:
                        lambda_plot(monthly,self.output/f"figures/fama_macbeth/{universe}__{sample_name}__spec8__combined.png")
                        for factor in ["MKT","SMB","HML","RMW","CMA"]:
                            lambda_plot(monthly,self.output/f"figures/fama_macbeth/{universe}__{sample_name}__spec8__{factor}.png",[factor])
                        diag=[]
                        for factor in ["MKT","SMB","HML","RMW","CMA"]:
                            s=monthly.set_index("return_month")[f"lambda_{factor}"].dropna()
                            diag.append({"universe":universe,"sample":sample_name,"factor":factor,"mean_lambda":s.mean(),
                                "std_lambda":s.std(),"min_lambda":s.min(),"max_lambda":s.max(),"share_positive":(s>0).mean(),
                                "share_negative":(s<0).mean(),"largest_positive_month":str(s.idxmax()),"largest_negative_month":str(s.idxmin())})
                        self.save_csv(pd.DataFrame(diag),f"fama_macbeth/lambda_diagnostics/{universe}__{sample_name}.csv")
        monthly=pd.concat(all_monthly,ignore_index=True); summary=pd.concat(all_summary,ignore_index=True); effective=pd.DataFrame(effective)
        self.save_csv(monthly,"fama_macbeth/monthly_lambdas/all.csv"); self.save_csv(summary,"fama_macbeth/summary_statistics/all.csv")
        self.save_csv(effective,"fama_macbeth/effective_samples.csv")
        for (universe,sample),group in summary.groupby(["universe","sample"]):
            path=self.output/f"tables/fm__{universe}__{sample}.csv"
            monthly_group=monthly.loc[(monthly.universe==universe)&(monthly["sample"]==sample)]
            fm_compact_table(group,path,monthly_group)
            self.artifacts.extend([self.display_path(path),self.display_path(path.with_suffix('.md'))])
        self.stage("fama_macbeth", "complete"); return summary, effective

    def run_grs(self,factors,assets,metadata):
        self.stage("time_series_grs", "running")
        all_regs=[]; all_grs=[]
        label=self.cfg["families"][self.grs_family]["label"]
        meta=metadata[metadata.family==self.grs_family]
        for sample_name in self.cfg["samples"]:
            resolved=self.resolve(factors,assets,sample_name); a,f=slice_sample(assets,resolved),slice_sample(factors,resolved)
            for model,names in self.cfg["models"].items():
                keys={"portfolio_family":self.grs_family,"portfolio_family_display_name":f"Size × {label}",
                    "sample":sample_name,"model":model}
                regs,residuals,f_used=portfolio_regressions(a,f,names,**keys)
                result,intermediate=grs_test(regs.alpha.to_numpy(),residuals,f_used[names].to_numpy())
                result.update(keys); all_grs.append(result); all_regs.append(regs)
                base=f"time_series/{self.grs_family}/{sample_name}/{model}"
                self.save_csv(regs,f"{base}__portfolio_regressions.csv")
                intermediate_path=self.output/f"{base}__grs_intermediates.json"
                write_json(intermediate_path,{**keys,**intermediate}); self.artifacts.append(self.display_path(intermediate_path))
                alpha,tstat=alpha_grids(regs,meta); alpha.to_csv(self.output/f"{base}__alpha_grid.csv"); tstat.to_csv(self.output/f"{base}__alpha_tstat_grid.csv")
                grid_plot(alpha,self.output/f"figures/time_series/{self.grs_family}__{sample_name}__{model}__alpha.png",f"Alpha grid — {model} — {sample_name}",label)
                grid_plot(tstat,self.output/f"figures/time_series/{self.grs_family}__{sample_name}__{model}__alpha_t.png",f"Alpha t-stat grid — {model} — {sample_name}",label)
        regs=pd.concat(all_regs,ignore_index=True); grs=pd.DataFrame(all_grs)
        self.save_csv(regs,f"time_series/{self.grs_family}/portfolio_regressions_all.csv"); self.save_csv(grs,f"time_series/{self.grs_family}/grs_results.csv")
        self.stage("time_series_grs", "complete"); return grs, regs

    def finish(self,two_pass,errors,hml,fm,fm_effective,grs,time_series,uni_audit, factors, panels, univariate, industries):
        self.stage("reporting","running")
        facts=build_facts(two_pass,errors,hml,fm,grs,time_series,fm_effective); write_json(self.output/"interpretation_facts.json",facts)
        self.save_csv(uni_audit,"tables/univariate_partition_audit.csv")
        pytest_summary={"status":"not_requested_for_development_run"}
        if self.production:
            test=subprocess.run([sys.executable,"-m","pytest","-q"],cwd=ROOT,text=True,capture_output=True)
            pytest_summary={"exit_code":test.returncode,"stdout":test.stdout[-4000:],"stderr":test.stderr[-2000:]}
            if test.returncode: raise RuntimeError("pytest failed during production QA")
        report_path = ROOT/"reports/assignment3_final_report.md" if self.production else self.output/"reports/assignment3_final_report.md"
        manifest_path = ROOT/"production_manifest.json" if self.production else self.output/"run_manifest.json"
        inventory=sorted(self.display_path(p) for p in self.output.rglob("*") if p.is_file())
        inventory.extend([self.display_path(report_path), self.display_path(manifest_path)])
        try: commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
        except Exception: commit=None
        headline_samples={name:next(value for key,value in self.samples.items() if key.startswith(name+":")) for name in self.cfg["samples"]}
        manifest={"run_timestamp":datetime.now(timezone.utc).isoformat(),"git_commit_if_available":commit,
            "python_version":platform.python_version(),"dependencies":{p:importlib.metadata.version(p) for p in ["pandas","numpy","scipy","statsmodels","matplotlib","PyYAML","requests","pytest"]},
            "source_urls":{k:v["url"] for k,v in self.source_manifest["sources"].items()},
            "source_download_timestamps":{k:v.get("downloaded_at") for k,v in self.source_manifest["sources"].items()},
            "data_hashes":{k:v.get("sha256") for k,v in self.source_manifest["sources"].items()},
            "factor_endpoint":str(factors.date.max()),
            "asset_endpoints":{**{k:str(v.date.max()) for k,v in panels.items()},"combined_univariate":str(univariate.date.max()),"industries_49":str(industries.date.max())},
            "actual_sample_periods":self.samples,"headline_sample_periods":headline_samples,
            "fm_effective_samples":fm_effective.to_dict("records"),
            "selected_grs_family":self.grs_family,"models":self.cfg["models"],
            "fm_specifications":self.cfg["specifications"],"rolling_window":self.cfg["rolling_window"],"hac_lags":self.cfg["hac_lags"],
            "pytest_summary":pytest_summary,"artifact_inventory":inventory,"configuration_hash":config_hash()}
        build_report(report_path,facts,manifest)
        write_json(manifest_path,manifest)
        self.stage("reporting","complete"); self.stage("final_qa","complete")

    def run(self):
        self.initialize_state()
        factors,panels,metadata,univariate,uni_audit,industries=self.acquire_build_validate()
        two_pass,errors,hml=self.run_two_pass(factors,panels)
        fm,fm_effective=self.run_fm(factors,{"combined_univariate":univariate,"industries_49":industries})
        grs,time_series=self.run_grs(factors,panels[self.grs_family],metadata)
        self.finish(two_pass,errors,hml,fm,fm_effective,grs,time_series,uni_audit,factors,panels,univariate,industries)


def parse_args():
    parser=argparse.ArgumentParser(description="BUFN741 Assignment 3 asset-pricing workflow")
    parser.add_argument("--production",action="store_true"); parser.add_argument("--grs-family")
    parser.add_argument("--refresh-data",action="store_true"); parser.add_argument("--skip-download",action="store_true")
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results")
    return parser.parse_args()


def main():
    logging.basicConfig(level=logging.INFO,format="%(levelname)s %(message)s"); args=parse_args()
    workflow=Workflow(args.output_dir,args.production,args.grs_family,args.refresh_data,args.skip_download)
    try: workflow.run()
    except Exception as exc:
        workflow.stage("final_qa","failed",str(exc)); LOG.error("Workflow failed: %s",exc); LOG.debug(traceback.format_exc()); raise


if __name__=="__main__": main()
