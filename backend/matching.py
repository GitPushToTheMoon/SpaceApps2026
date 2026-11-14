"""Finds the experiments closest to the user's conditions.

Plain Python on purpose: the AI never chooses which experiments count as evidence.
"""

from typing import List, Optional

import pandas as pd

from . import data
from .schemas import MatchedExperiment

# How far counts as "1 point" for each condition (makes units comparable)
SCALE_OXYGEN_PCT = 10.0
SCALE_PRESSURE_PSI = 5.0
SCALE_AIRFLOW_CM_S = 20.0

# Unknown condition: not a match, but not ruled out either.
# Slightly worse than a small known difference, so reported data wins ties.
MISSING_PENALTY = 0.75

# When the user picks a material, it should dominate the ranking
DIFFERENT_MATERIAL_PENALTY = 2.0   # same fuel type (e.g. both solids), different material
DIFFERENT_FUEL_TYPE_PENALTY = 3.0  # e.g. user picked a fabric, test burned a liquid droplet

# Thresholds for the coverage warnings (in each condition's own units)
GAP_OXYGEN_PCT = 3.0
GAP_PRESSURE_PSI = 2.0
GAP_AIRFLOW_CM_S = 10.0


def range_distance(value: float, low, high, scale: float) -> float:
    """0 if value is inside [low, high]; otherwise distance to the nearest edge / scale.
    One edge missing -> treated as a single value. Both missing -> MISSING_PENALTY."""
    low_missing, high_missing = pd.isna(low), pd.isna(high)
    if low_missing and high_missing:
        return MISSING_PENALTY
    if low_missing:
        low = high
    if high_missing:
        high = low
    if low > high:
        low, high = high, low
    if low <= value <= high:
        return 0.0
    return min(abs(value - low), abs(value - high)) / scale


def _raw_gap(value: float, low, high) -> Optional[float]:
    """Distance in real units (not scaled); None if the test didn't report it."""
    if pd.isna(low) and pd.isna(high):
        return None
    low = high if pd.isna(low) else low
    high = low if pd.isna(high) else high
    low, high = min(low, high), max(low, high)
    return 0.0 if low <= value <= high else min(abs(value - low), abs(value - high))


def find_matches(
    oxygen_pct: float,
    pressure_psi: float,
    airflow_cm_s: float,
    material: Optional[str] = None,
    fuel_type: Optional[str] = None,
    k: int = 5,
    df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Score every verified experiment and return the k closest (closest first),
    with a match_distance column plus the per-condition parts."""
    df = data.load_experiments() if df is None else df
    if df.empty:
        return df.assign(match_distance=pd.Series(dtype=float))

    out = df.copy()
    out["d_oxygen"] = [range_distance(oxygen_pct, lo, hi, SCALE_OXYGEN_PCT)
                       for lo, hi in zip(out["oxygen_pct_min"], out["oxygen_pct_max"])]
    out["d_pressure"] = [range_distance(pressure_psi, lo, hi, SCALE_PRESSURE_PSI)
                         for lo, hi in zip(out["pressure_psi_min"], out["pressure_psi_max"])]
    out["d_airflow"] = [range_distance(airflow_cm_s, lo, hi, SCALE_AIRFLOW_CM_S)
                        for lo, hi in zip(out["airflow_cm_s_min"], out["airflow_cm_s_max"])]

    out["d_material"] = 0.0
    if material:
        same_material = out["material"].fillna("").str.lower() == material.strip().lower()
        same_type = out["fuel_type"].fillna("").str.lower() == (fuel_type or "").strip().lower()
        out.loc[~same_material & same_type, "d_material"] = DIFFERENT_MATERIAL_PENALTY
        out.loc[~same_material & ~same_type, "d_material"] = DIFFERENT_FUEL_TYPE_PENALTY

    out["match_distance"] = (out["d_oxygen"] + out["d_pressure"] + out["d_airflow"]
                             + out["d_material"]).round(3)
    # tie-break: prefer tests that reported more of the conditions
    out["n_missing"] = sum(
        (out[lo].isna() & out[hi].isna()).astype(int)
        for lo, hi in [("oxygen_pct_min", "oxygen_pct_max"),
                       ("pressure_psi_min", "pressure_psi_max"),
                       ("airflow_cm_s_min", "airflow_cm_s_max")]
    )
    return out.sort_values(["match_distance", "n_missing", "id"]).head(k).reset_index(drop=True)


def to_matched_experiments(matches: pd.DataFrame) -> List[MatchedExperiment]:
    """DataFrame from find_matches -> API objects for the /assess response."""
    return [
        MatchedExperiment(**data.row_to_experiment(r).model_dump(),
                          match_distance=float(r["match_distance"]))
        for _, r in matches.iterrows()
    ]


def coverage_gaps(
    matches: pd.DataFrame,
    oxygen_pct: float,
    pressure_psi: float,
    airflow_cm_s: float,
    material: Optional[str] = None,
    gravity_g: float = 0.0,
) -> List[str]:
    """Data gaps worked out in code (not by the AI), always added to /assess data_gaps."""
    gaps: List[str] = []
    if matches.empty:
        return ["No verified experiments are loaded."]

    def closest(col_lo: str, col_hi: str, value: float) -> Optional[float]:
        vals = [_raw_gap(value, lo, hi) for lo, hi in zip(matches[col_lo], matches[col_hi])]
        vals = [v for v in vals if v is not None]
        return min(vals) if vals else None

    o = closest("oxygen_pct_min", "oxygen_pct_max", oxygen_pct)
    if o is None or o > GAP_OXYGEN_PCT:
        gaps.append(f"No closely matching tests at {oxygen_pct:g}% oxygen.")

    p = closest("pressure_psi_min", "pressure_psi_max", pressure_psi)
    if p is None:
        gaps.append("The closest tests did not report pressure.")
    elif p > GAP_PRESSURE_PSI:
        gaps.append(f"No closely matching tests at {pressure_psi:g} psi.")

    a = closest("airflow_cm_s_min", "airflow_cm_s_max", airflow_cm_s)
    if a is None:
        gaps.append("The closest tests did not report airflow.")
    elif a > GAP_AIRFLOW_CM_S:
        gaps.append(f"No closely matching tests at {airflow_cm_s:g} cm/s airflow.")

    if material:
        n_same = int((matches["material"].fillna("").str.lower() == material.strip().lower()).sum())
        total = int((data.load_experiments()["material"].fillna("").str.lower()
                     == material.strip().lower()).sum())
        if total == 0:
            gaps.append(f"No verified tests of {material} in the dataset.")
        elif n_same == 0:
            gaps.append(f"None of the closest tests used {material}.")
        elif total < 3:
            gaps.append(f"Only {total} verified test(s) of {material} in the dataset.")

    if gravity_g and gravity_g > 0:
        gaps.append("No partial-gravity combustion data yet; results are based on microgravity tests.")

    return gaps
