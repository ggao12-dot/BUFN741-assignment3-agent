from pathlib import Path
from src.reporting.build_report import build_report
from run_workflow import Workflow


def test_report_artifact_exists(tmp_path):
    path=tmp_path/"report.md";build_report(path,{},{});assert path.exists() and "GRS" in path.read_text()


def test_production_state_is_reset_at_run_start(tmp_path):
    workflow=Workflow(tmp_path/"out",True,None,False,True);workflow.state_path=tmp_path/"state.json"
    workflow.initialize_state()
    import json
    state=json.loads(workflow.state_path.read_text())
    assert set(v["status"] for v in state["stages"].values())=={"pending"}
