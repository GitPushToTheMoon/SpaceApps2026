"""Risk rules, evidence sentences and number checks for POST /assess.

Everything here is decided by code from the data, never by the AI:
- the risk level (rules below)
- the evidence sentences (built from the CSV values)
- a check that every number in the AI's explanation is a real value
"""
import re
from typing import List, Optional, Tuple

import pandas as pd

BURNED = {"burned", "ignited"}
OXYGEN_TOLERANCE_PCT = 1.0  # within 1% oxygen counts as "about the same"
DID_NOT_BURN = {"self-extinguished", "no ignition", "no spread", "blowoff"}

OUTCOME_PHRASES = {
    "burned": "burned",
    "ignited": "ignited and burned",
    "self-extinguished": "self-extinguished",
    "no ignition": "did not ignite",
    "no spread": "ignited but did not spread",
    "blowoff": "was blown out by the airflow",
    "other": "had a mixed or unclear result",
    "unknown": "had no outcome reported",
}


# ------------------------------------------------------------------ formatting helpers

def _num(v) -> Optional[float]:
    return None if v is None or (isinstance(v, float) and v != v) else float(v)


def fmt(v: float) -> str:
    return f"{v:g}"


def fmt_range(lo, hi, unit: str) -> Optional[str]:
    lo, hi = _num(lo), _num(hi)
    if lo is None and hi is None:
        return None
    lo = hi if lo is None else lo
    hi = lo if hi is None else hi
    lo, hi = min(lo, hi), max(lo, hi)
    return f"{fmt(lo)}{unit}" if lo == hi else f"{fmt(lo)}–{fmt(hi)}{unit}"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _max_oxygen(row) -> Optional[float]:
    vals = [_num(row.get("oxygen_pct_min")), _num(row.get("oxygen_pct_max"))]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def _min_oxygen(row) -> Optional[float]:
    vals = [_num(row.get("oxygen_pct_min")), _num(row.get("oxygen_pct_max"))]
    vals = [v for v in vals if v is not None]
    return min(vals) if vals else None


# ------------------------------------------------------------------ evidence

def evidence_sentence(row) -> str:
    """e.g. 'PMMA burned at 22–22.1% oxygen, 20 cm/s airflow (burn time 600 s).'"""
    what = row.get("material") or row.get("fuel_type") or "Sample"
    phrase = OUTCOME_PHRASES.get(row.get("outcome_category") or "unknown", "had an unclear result")
    conds = [c for c in [
        fmt_range(row.get("oxygen_pct_min"), row.get("oxygen_pct_max"), "% oxygen"),
        fmt_range(row.get("pressure_psi_min"), row.get("pressure_psi_max"), " psi"),
        fmt_range(row.get("airflow_cm_s_min"), row.get("airflow_cm_s_max"), " cm/s airflow"),
    ] if c]
    sentence = f"{what} {phrase}"
    if conds:
        sentence += " at " + ", ".join(conds)
    burn = re.search(r"[Bb]urn time:?\s*([\d.]+)\s*s", str(row.get("outcome") or ""))
    if burn and row.get("outcome_category") in BURNED:
        sentence += f" (burn time {burn.group(1)} s)"
    return sentence + "."


# ------------------------------------------------------------------ risk rules

def rule_risk(matches: pd.DataFrame, oxygen_pct: float,
              material: Optional[str], fuel_type: Optional[str]) -> Tuple[str, str]:
    """Returns (risk_level, reason). Rules, checked in order:
    high      - same material (or fuel type) burned at oxygen at or below the user's (within 1%)
    low       - same material only failed to burn, at oxygen at or above the user's (within 1%)
                (never "low" when no material was chosen: droplet tests going out
                 says nothing about cabin fabrics and plastics)
    elevated  - anything else with relevant tests (mixed, or burned only at higher oxygen)
    insufficient data - no tests of that material / fuel type among the matches
    """
    if matches.empty:
        return "insufficient data", "No verified experiments are loaded."

    if material:
        rel = matches[matches["material"].fillna("").str.lower() == material.lower()]
        label = material
    elif fuel_type:
        rel = matches[matches["fuel_type"].fillna("").str.lower() == fuel_type.lower()]
        label = f"{fuel_type} fuels"
    else:
        rel, label = matches, "the closest tests"

    if rel.empty:
        return "insufficient data", f"None of the closest tests used {label}."

    rows = rel.to_dict("records")
    burned_at_or_below = [r for r in rows if r.get("outcome_category") in BURNED
                          and _min_oxygen(r) is not None
                          and _min_oxygen(r) <= oxygen_pct + OXYGEN_TOLERANCE_PCT]
    if burned_at_or_below:
        lowest = min(_min_oxygen(r) for r in burned_at_or_below)
        where = "below" if lowest < oxygen_pct - OXYGEN_TOLERANCE_PCT else "about the same as"
        return "high", _cap(f"{label} burned at {fmt(lowest)}% oxygen, {where} "
                            f"the {fmt(oxygen_pct)}% you asked about.")

    failed = [r for r in rows if r.get("outcome_category") in DID_NOT_BURN]
    burned_any = [r for r in rows if r.get("outcome_category") in BURNED]
    failed_at_or_above = [r for r in failed
                          if _max_oxygen(r) is not None
                          and _max_oxygen(r) >= oxygen_pct - OXYGEN_TOLERANCE_PCT]
    if failed_at_or_above and not burned_any:
        if not material:
            return "elevated", ("The closest tests went out, but they are not cabin materials. "
                                "Pick a material for a specific answer.")
        highest = max(_max_oxygen(r) for r in failed_at_or_above)
        return "low", _cap(f"{label} did not sustain burning at {fmt(highest)}% oxygen, "
                           f"at or above the {fmt(oxygen_pct)}% you asked about.")

    if not material:
        return "elevated", ("The closest tests show mixed results. "
                            "Pick a material for a specific answer.")
    return "elevated", (f"The evidence for {label} is mixed or comes from different oxygen levels "
                        f"than the {fmt(oxygen_pct)}% you asked about.")


# ------------------------------------------------------------------ number check

_NUM_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(%|percent|psi|cm/s|s\b|seconds|g\b)", re.I)


def allowed_numbers(matches: pd.DataFrame, conditions: dict) -> List[float]:
    vals = [float(v) for v in conditions.values() if isinstance(v, (int, float))]
    for col in ["oxygen_pct_min", "oxygen_pct_max", "pressure_psi_min", "pressure_psi_max",
                "airflow_cm_s_min", "airflow_cm_s_max"]:
        vals += [float(v) for v in matches[col].tolist() if _num(v) is not None]
    for text in matches["outcome"].fillna("").tolist():  # burn times, lengths
        vals += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", text)]
    return vals


def numbers_ok(text: str, allowed: List[float], tolerance: float = 0.6) -> Tuple[bool, List[str]]:
    """Every number-with-unit in text must be within tolerance of a real value
    ('about 22%' for 22.1 is fine; '31.5%' for 22.1 is not)."""
    bad = []
    for num, unit in _NUM_UNIT.findall(text or ""):
        v = float(num)
        if not any(abs(v - a) <= tolerance for a in allowed):
            bad.append(f"{num}{unit}")
    return (not bad), bad


def template_explanation(risk_level: str, reason: str, evidence: List[Tuple[str, str]]) -> str:
    """Fallback when the AI is unavailable or gets a number wrong."""
    lines = " ".join(f"{s[:-1]} ({i})." for i, s in evidence[:3])
    return f"{lines} Risk is {risk_level}: {reason} This exact combination has not been tested."


# ------------------------------------------------------------------ stowage number check

_ANY_NUM = re.compile(r"(?<![A-Za-z\-])(\d+(?:\.\d+)?)")


def collect_numbers(obj) -> List[float]:
    """Every number inside a nested dict/list/str (scores, oxygen, sizes, days, names...)."""
    out: List[float] = []
    if isinstance(obj, bool) or obj is None:
        return out
    if isinstance(obj, (int, float)):
        if obj == obj:  # not NaN
            out.append(float(obj))
    elif isinstance(obj, str):
        out += [float(x) for x in re.findall(r"\d+(?:\.\d+)?", obj)]
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += collect_numbers(k) + collect_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out += collect_numbers(v)
    return out


def all_numbers_ok(text: str, allowed: List[float]) -> Tuple[bool, List[str]]:
    """Stricter than numbers_ok: checks EVERY number, with or without a unit
    (stowage text mentions bare scores like 'scored 79').
    - a number written with decimals (56.8) must match a real value exactly (within 0.05)
    - a whole number (34) may be a rounding of a real value (within 0.6)
    Numbers inside words or ids (e.g. 'Node1', 'PSI-69') are skipped; 0-10 are always
    allowed (counts like '2 laptops')."""
    bad = []
    for num in _ANY_NUM.findall(text or ""):
        v = float(num)
        tol = 0.05 if "." in num else 0.6
        if v <= 10 or any(abs(v - a) <= tol for a in allowed):
            continue
        bad.append(num)
    return (not bad), bad


# Numbers in context: a real value used with the wrong meaning ("14 tests" when 14 is an
# airflow) passes all_numbers_ok, so test counts and oxygen percentages get their own check.
_TESTS_NUM = re.compile(r"(?<![\w.\-])(\d+(?:\.\d+)?)\s+(?:[A-Za-z\-]+\s+){0,3}?(?:tests?|experiments?|runs?|trials?)\b",
                        re.IGNORECASE)
_PCT_NUM = re.compile(r"(?<![\w.\-])(\d+(?:\.\d+)?)\s*%")


def context_numbers_ok(text: str, test_counts: List[float], percents: List[float]) -> Tuple[bool, List[str]]:
    """'N tests' must be a real test count; 'N%' must be a real oxygen level, threshold or
    other percentage from the data. Returns (ok, offending strings)."""
    bad = []
    for num in _TESTS_NUM.findall(text or ""):
        if not any(abs(float(num) - t) < 1e-9 for t in test_counts):
            bad.append(f"{num} tests")
    for num in _PCT_NUM.findall(text or ""):
        tol = 0.05 if "." in num else 0.6
        if not any(abs(float(num) - p) <= tol for p in percents):
            bad.append(f"{num}%")
    return (not bad), bad
