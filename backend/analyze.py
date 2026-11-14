"""One-time pipeline: AI summaries for every verified experiment -> data/analysis.json

Run from the repo root:  python -m backend.analyze
"""
import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Dict

import pandas as pd
from pydantic import ValidationError

from . import ai
from .schemas import Analysis

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EXPERIMENTS_CSV = DATA_DIR / "experiments.csv"
ANALYSIS_JSON = DATA_DIR / "analysis.json"

ALLOWED_ENVIRONMENTS = {
    "spacecraft", "space station", "lunar base", "mars base", "pressurized rover", "earth",
}
ALLOWED_CATEGORIES = {"prevention", "detection", "suppression", "other"}
PAUSE_S = float(os.environ.get("ANALYZE_PAUSE_S", "1.0"))  # between calls, for rate limits

# Habitat rule (applied in code, not by the AI, so it's consistent):
# planned Moon/Mars habitats and rovers use higher oxygen and lower pressure.
HABITAT_ENVIRONMENTS = ["lunar base", "mars base", "pressurized rover"]
HABITAT_MIN_OXYGEN_PCT = 25.0
HABITAT_MAX_PRESSURE_PSI = 12.0


def habitat_relevant(row: dict) -> bool:
    oxygen = [v for v in (row.get("oxygen_pct_min"), row.get("oxygen_pct_max")) if v is not None]
    pressure = [v for v in (row.get("pressure_psi_min"), row.get("pressure_psi_max")) if v is not None]
    return (bool(oxygen) and max(oxygen) >= HABITAT_MIN_OXYGEN_PCT) or \
           (bool(pressure) and min(pressure) < HABITAT_MAX_PRESSURE_PSI)


def load_verified() -> pd.DataFrame:
    df = pd.read_csv(EXPERIMENTS_CSV, dtype={"id": str})
    verified = df["verified"].astype(str).str.strip().str.lower() == "yes"
    return df[verified].reset_index(drop=True)


def load_existing() -> Dict[str, dict]:
    if ANALYSIS_JSON.exists():
        return json.loads(ANALYSIS_JSON.read_text())
    return {}


def save(results: Dict[str, dict]) -> None:
    # write to a temp file first, then swap, so a crash never leaves a half-written file
    tmp = ANALYSIS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    tmp.replace(ANALYSIS_JSON)


def clean_row(row: pd.Series) -> dict:
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}


def apply_environment_rules(envs: list, row: dict) -> list:
    """spacecraft + space station always; Moon/Mars/rover exactly when the habitat rule says so;
    keep the AI's choice only for 'earth'."""
    out = ["spacecraft", "space station"]
    if habitat_relevant(row):
        out += HABITAT_ENVIRONMENTS
    if "earth" in (envs or []):
        out.append("earth")
    return out


def tidy(raw: dict, row: dict) -> dict:
    """Keep only allowed values and check the shape against schemas.Analysis."""
    raw = dict(raw)
    envs = [e for e in raw.get("environments") or [] if e in ALLOWED_ENVIRONMENTS]
    raw["environments"] = apply_environment_rules(envs, row)
    if raw.get("category") not in ALLOWED_CATEGORIES:
        raw["category"] = "other"
    score = raw.get("fire_safety_relevance")
    if isinstance(score, (int, float)):
        raw["fire_safety_relevance"] = max(1, min(10, int(round(score))))
    raw["key_findings"] = list(raw.get("key_findings") or [])[:3]
    return Analysis(**raw).model_dump()  # raises ValidationError if still malformed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI summaries into data/analysis.json")
    parser.add_argument("--redo", action="store_true", help="re-analyze experiments already done")
    parser.add_argument("--limit", type=int, help="only analyze this many (for testing)")
    parser.add_argument("--ids", nargs="+", help="only analyze these experiment ids")
    parser.add_argument("--fix-environments", action="store_true",
                        help="re-apply the environment rules to existing results (no AI calls)")
    args = parser.parse_args()

    df = load_verified()
    results = load_existing()

    if args.fix_environments:
        rows = {r["id"]: clean_row(r) for _, r in df.iterrows()}
        changed = 0
        for exp_id, entry in results.items():
            if exp_id in rows:
                new = apply_environment_rules(entry.get("environments"), rows[exp_id])
                if new != entry.get("environments"):
                    entry["environments"] = new
                    changed += 1
        save(results)
        print(f"Environment rules applied: {changed} of {len(results)} entries updated.")
        return

    todo = df
    if args.ids:
        todo = todo[todo["id"].isin(args.ids)]
    if not args.redo:
        todo = todo[~todo["id"].isin(results.keys())]
    if args.limit:
        todo = todo.head(args.limit)

    print(f"{len(df)} verified experiments, {len(results)} already analyzed, {len(todo)} to do "
          f"(model: {ai.MODEL}{', fallback: ' + ai.FALLBACK_MODEL if ai.FALLBACK_MODEL else ''})")

    done = failed = 0
    start = time.time()
    try:
        for i, (_, row) in enumerate(todo.iterrows(), 1):
            exp_id = row["id"]
            try:
                row_dict = clean_row(row)
                results[exp_id] = tidy(ai.analyze_experiment(row_dict), row_dict)
                save(results)
                done += 1
                print(f"[{i}/{len(todo)}] {exp_id}  relevance={results[exp_id]['fire_safety_relevance']}")
            except ai.AIUnavailable as e:
                failed += 1
                print(f"[{i}/{len(todo)}] {exp_id}  SKIPPED, Gemini unavailable: {e}")
            except (ValidationError, ValueError, TypeError) as e:
                failed += 1
                print(f"[{i}/{len(todo)}] {exp_id}  SKIPPED, bad AI output: {e}")
            if i < len(todo):
                time.sleep(PAUSE_S)
    except KeyboardInterrupt:
        print("\nStopped. Progress so far is saved; re-run to continue.")

    mins = (time.time() - start) / 60
    print(f"\nDone: {done} analyzed, {failed} skipped, {len(results)} total in {ANALYSIS_JSON.name} "
          f"({mins:.1f} min)")
    if failed:
        print("Re-run the same command to retry the skipped ones.")


if __name__ == "__main__":
    main()
