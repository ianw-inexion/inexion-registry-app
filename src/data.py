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
    from .config import IS_S3
    con = duckdb.connect(database=":memory:")
    if IS_S3:
        parquet_path = str(NHANES_PARQUET)
        try:
            con.execute("INSTALL httpfs; LOAD httpfs;")
            import os
            aws_key    = os.environ.get("AWS_ACCESS_KEY_ID", "")
            aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
            aws_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
            if aws_key:
                con.execute(f"""
                    SET s3_access_key_id='{aws_key}';
                    SET s3_secret_access_key='{aws_secret}';
                    SET s3_region='{aws_region}';
                """)
        except Exception:
            pass
    else:
        parquet_path = NHANES_PARQUET.as_posix()
    con.execute(
        f"CREATE OR REPLACE VIEW nhanes AS "
        f"SELECT * FROM '{parquet_path}'"
    )
    return con


def _build_where(filters: dict) -> tuple:
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


def cohort_count(filters: dict) -> int:
    con = get_connection()
    where, params = _build_where(filters)
    q = f"SELECT COUNT(*) AS n FROM nhanes{where}"
    return int(con.execute(q, params).fetchone()[0])


def cohort_preview(filters: dict, limit: int = 500) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    cols = (
        "seqn, cycle, age, sex, race_ethnicity, bmi, systolic_mean, diastolic_mean, "
        "albumin, creatinine, glucose_biopro, crp, rdw, wbc, phenoage, phenoage_delta, "
        "kdm_bioage, kdm_advance"
    )
    q = f"SELECT {cols} FROM nhanes{where} LIMIT {int(limit)}"
    return con.execute(q, params).df()


def _to_float(v):
    """Coerce a possibly-None / Decimal / numpy value to plain float or None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    return f


def _cohort_summary_unweighted(con, where, params) -> dict:
    q = f"""
        SELECT
            COUNT(*) AS n,
            CAST(AVG(age) AS DOUBLE)                                         AS mean_age,
            CAST(AVG(CASE WHEN sex = 2 THEN 1.0 ELSE 0.0 END) AS DOUBLE)     AS pct_female,
            CAST(AVG(bmi) AS DOUBLE)                                         AS mean_bmi,
            CAST(AVG(phenoage) AS DOUBLE)                                    AS mean_phenoage,
            CAST(AVG(phenoage_delta) AS DOUBLE)                              AS mean_phenoage_delta,
            CAST(STDDEV(phenoage_delta) AS DOUBLE)                           AS sd_phenoage_delta,
            CAST(AVG(kdm_bioage) AS DOUBLE)                                  AS mean_kdm,
            CAST(AVG(kdm_advance) AS DOUBLE)                                 AS mean_kdm_advance,
            CAST(AVG(systolic_mean) AS DOUBLE)                               AS mean_systolic,
            CAST(AVG(glucose_biopro) AS DOUBLE)                              AS mean_glucose,
            CAST(AVG(crp) AS DOUBLE)                                         AS mean_crp,
            CAST(AVG(hba1c) AS DOUBLE)                                       AS mean_hba1c,
            CAST(COUNT(*) AS DOUBLE)                                         AS effective_n,
            'unweighted'                                                     AS estimator
        FROM nhanes{where}
    """
    row = con.execute(q, params).df().iloc[0].to_dict()
    return {
        "n":                   int(row["n"]) if row["n"] is not None else 0,
        "mean_age":            _to_float(row["mean_age"]),
        "pct_female":          _to_float(row["pct_female"]),
        "mean_bmi":            _to_float(row["mean_bmi"]),
        "mean_phenoage":       _to_float(row["mean_phenoage"]),
        "mean_phenoage_delta": _to_float(row["mean_phenoage_delta"]),
        "sd_phenoage_delta":   _to_float(row["sd_phenoage_delta"]),
        "mean_kdm":            _to_float(row["mean_kdm"]),
        "mean_kdm_advance":    _to_float(row["mean_kdm_advance"]),
        "mean_systolic":       _to_float(row["mean_systolic"]),
        "mean_glucose":        _to_float(row["mean_glucose"]),
        "mean_crp":            _to_float(row["mean_crp"]),
        "mean_hba1c":          _to_float(row["mean_hba1c"]),
        "effective_n":         _to_float(row["effective_n"]),
        "estimator":           "unweighted",
    }


def _cohort_summary_weighted(con, where, params) -> dict:
    """
    Weighted variant - all aggregates explicitly cast to DOUBLE so DuckDB
    cannot return DECIMAL or NUMERIC types that pandas converts to object
    dtype, which then break Python f-string formatting downstream.
    """
    def wm(col_expr: str) -> str:
        return (
            f"CAST(SUM(CASE WHEN ({col_expr}) IS NOT NULL AND exam_weight_adj > 0 "
            f"THEN CAST(({col_expr}) AS DOUBLE) * CAST(exam_weight_adj AS DOUBLE) "
            f"ELSE 0.0 END) / "
            f"NULLIF(SUM(CASE WHEN ({col_expr}) IS NOT NULL AND exam_weight_adj > 0 "
            f"THEN CAST(exam_weight_adj AS DOUBLE) ELSE 0.0 END), 0.0) AS DOUBLE)"
        )

    q = f"""
        SELECT
            COUNT(*) AS n,
            {wm('age')}                                       AS mean_age,
            {wm('CASE WHEN sex = 2 THEN 1.0 ELSE 0.0 END')}   AS pct_female,
            {wm('bmi')}                                       AS mean_bmi,
            {wm('phenoage')}                                  AS mean_phenoage,
            {wm('phenoage_delta')}                            AS mean_phenoage_delta,
            CAST(STDDEV(phenoage_delta) AS DOUBLE)            AS sd_phenoage_delta,
            {wm('kdm_bioage')}                                AS mean_kdm,
            {wm('kdm_advance')}                               AS mean_kdm_advance,
            {wm('systolic_mean')}                             AS mean_systolic,
            {wm('glucose_biopro')}                            AS mean_glucose,
            {wm('crp')}                                       AS mean_crp,
            {wm('hba1c')}                                     AS mean_hba1c,
            CAST(
                POWER(CAST(SUM(exam_weight_adj) AS DOUBLE), 2) /
                NULLIF(SUM(CAST(exam_weight_adj AS DOUBLE) *
                           CAST(exam_weight_adj AS DOUBLE)), 0.0)
            AS DOUBLE)                                        AS effective_n,
            'weighted'                                        AS estimator
        FROM nhanes{where}
    """
    row = con.execute(q, params).df().iloc[0].to_dict()
    return {
        "n":                   int(row["n"]) if row["n"] is not None else 0,
        "mean_age":            _to_float(row["mean_age"]),
        "pct_female":          _to_float(row["pct_female"]),
        "mean_bmi":            _to_float(row["mean_bmi"]),
        "mean_phenoage":       _to_float(row["mean_phenoage"]),
        "mean_phenoage_delta": _to_float(row["mean_phenoage_delta"]),
        "sd_phenoage_delta":   _to_float(row["sd_phenoage_delta"]),
        "mean_kdm":            _to_float(row["mean_kdm"]),
        "mean_kdm_advance":    _to_float(row["mean_kdm_advance"]),
        "mean_systolic":       _to_float(row["mean_systolic"]),
        "mean_glucose":        _to_float(row["mean_glucose"]),
        "mean_crp":            _to_float(row["mean_crp"]),
        "mean_hba1c":          _to_float(row["mean_hba1c"]),
        "effective_n":         _to_float(row["effective_n"]),
        "estimator":           "weighted",
    }


def cohort_summary(filters: dict, weighted: bool = False) -> dict:
    """
    Descriptive summary for the cohort.

    weighted=True applies NHANES exam_weight_adj. Means become survey-weighted
    (nationally representative population estimates). If the weighted SQL
    fails for any reason on a deployed environment, we silently fall back to
    the unweighted estimator and tag the result with estimator='unweighted'.
    """
    con = get_connection()
    where, params = _build_where(filters)
    if not weighted:
        return _cohort_summary_unweighted(con, where, params)
    try:
        return _cohort_summary_weighted(con, where, params)
    except Exception:
        out = _cohort_summary_unweighted(con, where, params)
        out["estimator"] = "unweighted (fallback)"
        return out


def cohort_export(filters: dict, max_rows: int = 100_000) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    q = f"SELECT * FROM nhanes{where} LIMIT {int(max_rows)}"
    return con.execute(q, params).df()


def distribution(col: str, filters: dict, bin_count: int = 40) -> pd.DataFrame:
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


def trend_by_cycle(col: str, filters: dict, weighted: bool = False) -> pd.DataFrame:
    con = get_connection()
    where, params = _build_where(filters)
    glue = "AND" if where else "WHERE"

    if weighted:
        q = f"""
            SELECT
                cycle,
                COUNT(*) AS n,
                CAST(SUM(CAST({col} AS DOUBLE) * CAST(exam_weight_adj AS DOUBLE)) /
                     NULLIF(SUM(CAST(exam_weight_adj AS DOUBLE)), 0.0)
                    AS DOUBLE) AS mean_value,
                CAST(MEDIAN({col}) AS DOUBLE) AS median_value
            FROM nhanes{where}
            {glue} {col} IS NOT NULL AND exam_weight_adj > 0
            GROUP BY cycle
            ORDER BY cycle
        """
    else:
        q = f"""
            SELECT
                cycle,
                COUNT(*) AS n,
                CAST(AVG({col}) AS DOUBLE) AS mean_value,
                CAST(MEDIAN({col}) AS DOUBLE) AS median_value
            FROM nhanes{where}
            {glue} {col} IS NOT NULL
            GROUP BY cycle
            ORDER BY cycle
        """
    return con.execute(q, params).df()


def dataset_stats() -> dict:
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
