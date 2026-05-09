"""
Survey-weighted statistics helpers for population-representative estimates.

NHANES uses `exam_weight_adj` (interview/exam sample weights, divided by the
number of survey cycles spanned). HRS uses `survey_weight` (RAND HRS Wave 13
respondent weight, R13WTRESP). MIDUS does not provide a public weight — pass
weights=None and the helpers fall back to unweighted estimates.

Design principles:
- Drop NaN rows in (value, weight) pairs *together* before computing.
- Drop zero or negative weights — they're typically out-of-scope respondents.
- Match the unweighted definition exactly when weights=None or all-equal.
- Wilson-style or normal-approx CIs are NOT computed here — Phase 3.2 covers
  bootstrap CIs separately. These helpers return point estimates only.
"""
from __future__ import annotations
from typing import Optional, Sequence
import numpy as np
import pandas as pd


def _clean(values, weights):
    """Coerce to arrays, drop NaN + non-positive weights jointly."""
    v = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    if weights is None:
        w = np.ones_like(v, dtype=float)
    else:
        w = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(dtype=float)
    if v.shape != w.shape:
        raise ValueError(f"values shape {v.shape} != weights shape {w.shape}")
    mask = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return v[mask], w[mask]


def weighted_mean(values, weights=None) -> float:
    v, w = _clean(values, weights)
    if v.size == 0 or w.sum() == 0:
        return float("nan")
    return float(np.average(v, weights=w))


def weighted_var(values, weights=None) -> float:
    """Weighted variance (population form: divisor = sum of weights)."""
    v, w = _clean(values, weights)
    if v.size == 0 or w.sum() == 0:
        return float("nan")
    m = np.average(v, weights=w)
    return float(np.average((v - m) ** 2, weights=w))


def weighted_std(values, weights=None) -> float:
    var = weighted_var(values, weights)
    return float(np.sqrt(var)) if np.isfinite(var) else float("nan")


def weighted_quantile(values, q: float, weights=None) -> float:
    """
    Type-7 weighted quantile (linear interpolation between order statistics).
    `q` in [0, 1].
    """
    v, w = _clean(values, weights)
    if v.size == 0 or w.sum() == 0:
        return float("nan")
    order = np.argsort(v)
    v = v[order]
    w = w[order]
    cum = np.cumsum(w)
    cutoff = q * cum[-1]
    idx = np.searchsorted(cum, cutoff, side="left")
    idx = min(idx, len(v) - 1)
    return float(v[idx])


def weighted_median(values, weights=None) -> float:
    return weighted_quantile(values, 0.5, weights)


def weighted_pct(condition, weights=None) -> float:
    """Weighted proportion where `condition` is a 0/1 or boolean array."""
    return weighted_mean(condition, weights)


def weighted_quantile_bins(values, q_breaks: Sequence[float], weights=None,
                           labels: Optional[Sequence[str]] = None) -> pd.Categorical:
    """
    Survey-weighted analogue of pd.qcut. Returns a Categorical assigning every
    row of `values` to a bin defined by weighted quantiles.

    q_breaks: e.g. [0, 0.2, 0.4, 0.6, 0.8, 1.0] for quintiles.
    """
    v_full = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    edges = [weighted_quantile(values, q, weights) for q in q_breaks]
    edges = np.array(edges, dtype=float)
    # pd.cut handles NaN already; nudge edges slightly to keep them strictly increasing
    for i in range(1, len(edges)):
        if edges[i] <= edges[i - 1]:
            edges[i] = edges[i - 1] + 1e-9
    return pd.cut(v_full, bins=edges, labels=labels, include_lowest=True)


def effective_n(weights) -> float:
    """
    Kish's effective sample size: (sum w)^2 / sum(w^2). Useful as a sanity
    check on how much the weights are concentrated.
    """
    w = pd.to_numeric(pd.Series(weights), errors="coerce").to_numpy(dtype=float)
    w = w[np.isfinite(w) & (w > 0)]
    if w.size == 0:
        return 0.0
    s1 = w.sum()
    s2 = (w * w).sum()
    return float(s1 * s1 / s2) if s2 > 0 else 0.0


def weighted_summary(df: pd.DataFrame, cols: Sequence[str],
                     weight_col: Optional[str] = None) -> pd.DataFrame:
    """
    Build a tidy summary table: one row per column, with weighted n / mean / sd
    / median / q25 / q75. If weight_col is None or missing, returns unweighted
    stats.
    """
    out = []
    w = df[weight_col].to_numpy() if weight_col and weight_col in df.columns else None
    for c in cols:
        if c not in df.columns:
            continue
        v = df[c].to_numpy()
        out.append({
            "variable": c,
            "n": int(np.isfinite(pd.to_numeric(pd.Series(v), errors="coerce")).sum()),
            "mean": weighted_mean(v, w),
            "sd":   weighted_std(v, w),
            "p25":  weighted_quantile(v, 0.25, w),
            "median": weighted_median(v, w),
            "p75":  weighted_quantile(v, 0.75, w),
        })
    return pd.DataFrame(out)
