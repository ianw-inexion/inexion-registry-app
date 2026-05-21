"""
Run manifest and report-writing helpers.

Every hypothesis script produces an inex_analysis_run-compatible JSON manifest
plus a branded HTML report through these utilities. Keeps the per-script code
focused on the hypothesis logic.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

# Make src.config importable when the hypothesis script is executed directly.
ANALYTICS_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ANALYTICS_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.config import NHANES_PARQUET, IS_S3, data_exists  # noqa: E402

RUNS_DIR = ANALYTICS_DIR / "runs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


@dataclass
class RunManifest:
    run_id: str
    hypothesis_id: str
    cohort_definition: dict
    methods: dict
    reference_cohort_version: str
    code_commit_hash: str
    ran_at: str
    output_uri: str
    data_partner_ids: list[str]
    synthetic_data_flag: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_nhanes_reference(cols: list[str] | None = None) -> pd.DataFrame:
    """Production Bronze read for NHANES. Returns a pandas DataFrame."""
    if cols is None:
        cols = [
            "seqn", "cycle", "cycle_start_year",
            "age", "sex", "race_ethnicity", "bmi",
            "phenoage", "phenoage_delta",
            "total_cholesterol", "hdl", "systolic_mean",
            "exam_weight",
        ]
    if not data_exists(NHANES_PARQUET):
        raise FileNotFoundError(
            f"NHANES parquet not found at {NHANES_PARQUET}. "
            "Confirm INEXION_BUCKET_ROOT or INEXION_DATA_DIR is set correctly."
        )
    con = duckdb.connect(database=":memory:")
    if IS_S3:
        con.execute("INSTALL httpfs; LOAD httpfs;")
    path_str = str(NHANES_PARQUET) if IS_S3 else NHANES_PARQUET.as_posix()
    df = con.execute(
        f"SELECT {', '.join(cols)} FROM read_parquet('{path_str}') "
        f"WHERE phenoage IS NOT NULL AND age IS NOT NULL AND bmi IS NOT NULL "
        f"AND sex IS NOT NULL"
    ).df()
    df["source"] = "nhanes"
    return df


def make_run_dir(hypothesis_id: str, run_id: str | None = None) -> tuple[Path, str, str]:
    run_id = run_id or uuid.uuid4().hex[:12]
    started_at = datetime.now(timezone.utc).isoformat()
    output_dir = RUNS_DIR / f"{hypothesis_id}_{started_at[:10]}_{run_id}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir, run_id, started_at


def write_run(
    output_dir: Path,
    manifest: RunManifest,
    results: dict,
    extras: dict[str, pd.DataFrame] | None = None,
):
    (output_dir / "manifest.json").write_text(json.dumps(manifest.to_dict(), indent=2))
    (output_dir / "results.json").write_text(json.dumps(results, indent=2, default=str))
    if extras:
        for name, df in extras.items():
            df.to_parquet(output_dir / f"{name}.parquet", index=False)

    # Render HTML report if template available
    try:
        from analytics.templates.report import render_report
        report_html = render_report(manifest.to_dict(), results)
        (output_dir / "report.html").write_text(report_html)
    except Exception as exc:
        logging.getLogger("manifest").warning("Report rendering skipped: %s", exc)


def code_commit_hash() -> str:
    return os.environ.get("GIT_COMMIT", "uncommitted")
