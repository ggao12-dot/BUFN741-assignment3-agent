from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import requests
import zipfile

from src.data.metadata import SOURCE_FILES, source_url


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_cache(raw_dir: Path) -> dict:
    """Validate that an offline cache is complete and matches its manifest."""
    manifest_path = raw_dir / "source_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Cached data require data/raw/source_manifest.json")
    manifest = json.loads(manifest_path.read_text())
    sources = manifest.get("sources", {})
    for source_id, filename in SOURCE_FILES.items():
        target = raw_dir / filename
        if not target.exists():
            raise FileNotFoundError(f"Cached source is missing: {target}")
        if not zipfile.is_zipfile(target):
            raise RuntimeError(f"Cached file is not a valid ZIP: {target}")
        expected = sources.get(source_id, {}).get("sha256")
        if not expected:
            raise RuntimeError(f"Cache manifest has no hash for {source_id}")
        if sha256(target) != expected:
            raise RuntimeError(f"Cached file hash differs from manifest: {target}")
    return manifest


def download_all(raw_dir: Path, refresh: bool = False, timeout: int = 90) -> dict:
    """Download authoritative ZIPs, preserving cache and source provenance."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "source_manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"sources": {}}
    sources = dict(old.get("sources", {}))
    session = requests.Session()
    session.headers["User-Agent"] = "BUFN741 reproducible research harness/1.0"
    for source_id, filename in SOURCE_FILES.items():
        target = raw_dir / filename
        if target.exists() and not refresh:
            if not zipfile.is_zipfile(target):
                raise RuntimeError(f"Cached file is not a valid ZIP: {target}; use --refresh-data")
            expected_hash = sources.get(source_id, {}).get("sha256")
            actual_hash = sha256(target)
            if expected_hash and expected_hash != actual_hash:
                raise RuntimeError(f"Cached file hash differs from manifest: {target}; use --refresh-data")
            continue
        response = session.get(source_url(source_id), timeout=timeout)
        response.raise_for_status()
        if not response.content.startswith(b"PK"):
            raise RuntimeError(f"{source_id}: response is not a ZIP archive")
        target.write_bytes(response.content)
        sources[source_id] = {
            "url": source_url(source_id), "filename": filename,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "sha256": sha256(target), "bytes": target.stat().st_size,
        }
    # Backfill provenance for preexisting cache files.
    for source_id, filename in SOURCE_FILES.items():
        target = raw_dir / filename
        if target.exists() and source_id not in sources:
            sources[source_id] = {"url": source_url(source_id), "filename": filename,
                "downloaded_at": None, "sha256": sha256(target), "bytes": target.stat().st_size}
    manifest = {"library": "Kenneth R. French Data Library", "sources": sources}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
