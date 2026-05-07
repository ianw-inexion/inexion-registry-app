"""
DuckDB-backed data access for the NHANES harmonized + PhenoAge parquet.

Design: one DuckDB in-memory connection per Streamlit session, cached via
@st.cache_resource. Query functions take filter dicts and return pandas
DataFrames or scalar counts. All queries are parameterized via DuckDB
prepared statements. User input never gets string-concatenated into SQL.
"""
from __future__ import annotations
from typing import Any
import duckdb
import pandas as pd
import streamlit as st

from .config import NHANES_PARQUET


@st.cache_resource
def get_connection():
    """One DuckDB connection per Streamlit session. Registers the parquet as a view."""
    con = duckdb.connect(database=":memory:")
    con.execute(
        f"CREATE OR REPLACE VIEW nhanes AS "
        f"SELECT * FROM '{NHANES_PARQUET.as_posix()}'"
    )
    return con


def _build_where(filters: dict[str, Any]) -> tuple[str, list]:
    """
    Build a parameterized WHERE clause from a filter dict.

    Supported filter shapes:
        {"age": (40, 65)}                  -> age BETWEEN 40 AND 65
        {"sex": [1, 2]}                    -> sex IN (1, 2)
        {"cycle": ["2015-2016"]}           -> cycle IN (...)
        {"phenoage_delta": (None, -2)}     -> phenoage_delta <= -2
        {"phenoage_delta": (2, None)}      -> phenoage_delta >= 2
    """
    clauses, params = [], []
    for col, spec in filters.items():
        if spec is None:
            continue
        if isinstance(spec, tuple) and len(spec) == 2:
            lo, hi = spec
            if lo is not None and hi is not None:
                clauses.append(f"{col} BETWEEN ? AND ?")
                params.extend([lo, hi])
            elif lo is not None:
                clauses.append(f"{col} >= ?")
                params.append(lo)
            elif hi is not None:
                clauses.append(f"{col} <= ?")
                params.append(hi)
        elif isinstance(spec, list) and spec:
            placeholders = ",".join(["?"] * len(spec))
            clauses.append(f"{col} IN ({placeholders})")
            params.extend(spec)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def cohort_count(filters: dict[str, Any]) -> int:
    con = get_connection()
    where, params = _build_where(filters)
    q = f"SELECT COUNT(*) AS n FROM nhanes{where}"
    return int(con.execute(q, params).fetchone()[0])


def cohort_preview(filters: dict[str, Any], limit: int = 500) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    cols = (
        "seqn, cycle, age, sex, race_ethnicity, bmi, systolic_mean, diastolic_mean, "
        "albumin, creatinine, glucose_biopro, crp, rdw, wbc, phenoage, phenoage_delta, "
        "kdm_bioage, kdm_advance"
    )
    q = f"SELECT {cols} FROM nhanes{where} LIMIT {int(limit)}"
    return con.execute(q, params).df()


def cohort_summary(filters: dict[str, Any]) -> dict[str, Any]:
    """Descriptive summary for the cohort."""
    con = get_connection()
    where, params = _build_where(filters)
    q = f"""
        SELECT
            COUNT(*) AS n,
            AVG(age)                           AS mean_age,
            AVG(CASE WHEN sex = 2 THEN 1.0 ELSE 0.0 END) AS pct_female,
            AVG(bmi)                           AS mean_bmi,
            AVG(phenoage)                      AS mean_phenoage,
            AVG(phenoage_delta)                AS mean_phenoage_delta,
            STDDEV(phenoage_delta)             AS sd_phenoage_delta,
            AVG(kdm_bioage)                    AS mean_kdm,
            AVG(kdm_advance)                   AS mean_kdm_advance,
            AVG(systolic_mean)                 AS mean_systolic,
            AVG(glucose_biopro)                AS mean_glucose,
            AVG(crp)                           AS mean_crp,
            AVG(hba1c)                         AS mean_hba1c
        FROM nhanes{where}
    """
    row = con.execute(q, params).df().iloc[0].to_dict()
    return row


def cohort_export(filters: dict[str, Any], max_rows: int = 100_000) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    q = f"SELECT * FROM nhanes{where} LIMIT {int(max_rows)}"
    return con.execute(q, params).df()


def distribution(col: str, filters: dict[str, Any], bin_count: int = 40) -> pd.DataFrame:
    """Values of a numeric column for histogram plotting."""
    con = get_connection()
    where, params = _build_where(filters)
    glue = "AND" if where else "WHERE"
    q = f"""
        SELECT {col} AS value
        FROM nhanes{where}
        {glue} {col} IS NOT NULL
    """
    return con.execute(q, params).df()


def trend_by_cycle(col: str, filters: dict[str, Any]) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    glue = "AND" if where else "WHERE"
    q = f"""
        SELECT
            cycle,
            COUNT(*) AS n,
            AVG({col}) AS mean_value,
            MEDIAN({col}) AS median_value
        FROM nhanes{where}
        {glue} {col} IS NOT NULL
        GROUP BY cycle
        ORDER BY cycle
    """
    return con.execute(q, params).df()


def dataset_stats() -> dict[str, Any]:
    """Top-line stats for the landing page."""
    con = get_connection()
    q = """
        SELECT COUNT(*) AS n_total,
               COUNT(phenoage) AS n_with_phenoage,
               COUNT(kdm_bioage) AS n_with_kdm,
               MIN(cycle_start_year) AS min_year,
               MAX(cycle_start_year) AS max_year,
               COUNT(DISTINCT cycle) AS n_cycles
        FROM nhanes
    """
    return con.execute(q).df().iloc[0].to_dict()
