from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json
import yaml

ROOT = Path(__file__).resolve().parents[2]
FACTOR_COLUMNS = ["MKT", "SMB", "HML", "RMW", "CMA"]


def load_yaml(name: str) -> dict[str, Any]:
    with (ROOT / "config" / name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for name in ("models.yaml", "samples.yaml", "asset_universes.yaml", "fama_macbeth_specs.yaml", "workflow.yaml"):
        cfg.update(load_yaml(name))
    cfg["specifications"] = {int(k): v for k, v in cfg["specifications"].items()}
    return cfg


def config_hash() -> str:
    payload = b"".join((ROOT / "config" / p).read_bytes() for p in sorted(x.name for x in (ROOT / "config").glob("*.yaml")))
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")

