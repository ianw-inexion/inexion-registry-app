"""
Run loader - discover and parse analytics/runs/ output.

Each hypothesis script writes a timestamped directory under analytics/runs/
containing manifest.json, results.json, and optional extras parquets. The
partner-facing Streamlit pages use this module to pick the latest run per
hypothesis, parse its JSON payload, and surface results without having to
re-read filesystem in every page.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

ANALYTICS_DIR = Path(__file__).resolve().parents[1]
RUNS_DIR = ANALYTICS_DIR / "runs"


@dataclass
class RunRecord:
    hypothesis_id: str
    run_id: str
    run_date: str
    output_dir: Path
    manifest: dict
    results: dict

    @property
    def ran_at(self) -> str:
        return self.manifest.get("ran_at", "")

    def extras(self, name: str) -> Optional[pd.DataFrame]:
        """Read a parquet extra (e.g. 'cohort', 'matched_reference')."""
        path = self.output_dir / f"{name}.parquet"
        if path.exists():
            return pd.read_parquet(path)
        return None


def _parse_run_dir(d: Path) -> Optional[RunRecord]:
    if not d.is_dir():
        return None
    manifest_p = d / "manifest.json"
    results_p = d / "results.json"
    if not manifest_p.exists() or not results_p.exists():
        return None
    try:
        manifest = json.loads(manifest_p.read_text())
        results = json.loads(results_p.read_text())
    except Exception:
        return None
    # Canonical hypothesis_id comes from the manifest; the directory name
    # is parsed only to recover run_date and run_id where present.
    hypothesis_id = manifest.get("hypothesis_id") or results.get("hypothesis_id")
    if not hypothesis_id:
        return None
    parts = d.name.rsplit("_", 2)
    if len(parts) == 3:
        _, run_date, run_id = parts
    else:
        run_date = manifest.get("ran_at", "")[:10]
        run_id = manifest.get("run_id", "")
    return RunRecord(
        hypothesis_id=hypothesis_id,
        run_id=run_id,
        run_date=run_date,
        output_dir=d,
        manifest=manifest,
        results=results,
    )


def list_all_runs() -> List[RunRecord]:
    """All parseable runs across all hypotheses, newest first."""
    if not RUNS_DIR.exists():
        return []
    runs = []
    for d in RUNS_DIR.iterdir():
        rec = _parse_run_dir(d)
        if rec is not None:
            runs.append(rec)
    runs.sort(key=lambda r: r.ran_at, reverse=True)
    return runs


def latest_run(hypothesis_id: str) -> Optional[RunRecord]:
    """Most recent run matching the hypothesis_id."""
    matches = [r for r in list_all_runs() if r.hypothesis_id == hypothesis_id]
    if not matches:
        return None
    return matches[0]


def latest_runs_by_hypothesis(hypothesis_ids: List[str]) -> Dict[str, RunRecord]:
    """Map hypothesis_id -> latest RunRecord, omitting any not found."""
    out: Dict[str, RunRecord] = {}
    for hid in hypothesis_ids:
        rec = latest_run(hid)
        if rec is not None:
            out[hid] = rec
    return out


def runs_for_partner(partner_prefix: str) -> List[RunRecord]:
    """All latest runs whose hypothesis_id starts with the partner prefix
    (e.g. 'HEALTHSPAN' or 'AGELESSRX'). Deduped to latest per hypothesis."""
    by_hyp: Dict[str, RunRecord] = {}
    for r in list_all_runs():
        if not r.hypothesis_id.startswith(partner_prefix):
            continue
        existing = by_hyp.get(r.hypothesis_id)
        if existing is None or r.ran_at > existing.ran_at:
            by_hyp[r.hypothesis_id] = r
    return sorted(by_hyp.values(), key=lambda r: r.hypothesis_id)


def format_ran_at(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso
