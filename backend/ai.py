"""Every Gemini call lives here. Keys and credentials never leave the backend.

Settings (.env):
  GEMINI_MODEL           main model, e.g. gemini-2.5-flash
  GEMINI_FALLBACK_MODEL  optional backup model used if the main one is overloaded
  USE_VERTEX             "true" to use Vertex AI (Google Cloud credits), else AI Studio key
  GEMINI_API_KEY         AI Studio key (when USE_VERTEX is not true)
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS  (Vertex)
"""
import json
import re
import os
import time
from typing import Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv()

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL") or None
USE_VERTEX = os.environ.get("USE_VERTEX", "").lower() in ("1", "true", "yes")
# Optional: limit "thinking" so answers come back faster (fewer 504 timeouts).
#   GEMINI_THINKING_LEVEL=low       (newer models: "low"/"medium"/"high"/"minimal")
#   GEMINI_THINKING_BUDGET=0        (older 2.5 models: token budget, 0 = off)
THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL") or None
THINKING_BUDGET = os.environ.get("GEMINI_THINKING_BUDGET")

RETRYABLE = {429, 500, 503, 504}   # rate limit / overloaded / temporary server errors
MAX_ATTEMPTS = 4                   # per model
BASE_DELAY_S = 2                   # waits 2s, 4s, 8s between attempts

_client = None


class AIUnavailable(Exception):
    """Raised when every attempt on every model failed. main.py turns this into a 502."""


def client():
    """One shared client. Retries are handled below, so the library's own retry is off."""
    global _client
    if _client is None:
        http = types.HttpOptions(
            timeout=60_000,  # ms
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        if USE_VERTEX:
            _client = genai.Client(
                vertexai=True,
                project=os.environ["GOOGLE_CLOUD_PROJECT"],
                location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
                http_options=http,
            )
        else:
            _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=http)
    return _client


def _thinking_config() -> Optional[types.ThinkingConfig]:
    if THINKING_LEVEL:
        return types.ThinkingConfig(thinking_level=THINKING_LEVEL)
    if THINKING_BUDGET not in (None, ""):
        return types.ThinkingConfig(thinking_budget=int(THINKING_BUDGET))
    return None


def _call(model: str, prompt: str) -> dict:
    resp = client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            thinking_config=_thinking_config(),
        ),
    )
    # read only the text parts (skips hidden "thought_signature" parts, no warning)
    parts = resp.candidates[0].content.parts if resp.candidates and resp.candidates[0].content else []
    text = "".join(p.text for p in (parts or []) if getattr(p, "text", None)).strip()
    if not text:
        raise ValueError("Empty response from Gemini")
    return json.loads(text)


def ask_json(prompt: str) -> dict:
    """Send a prompt, get parsed JSON back. Retries busy/overloaded errors, then tries the fallback model."""
    models = [MODEL] + ([FALLBACK_MODEL] if FALLBACK_MODEL and FALLBACK_MODEL != MODEL else [])
    last_error: Optional[Exception] = None

    for model in models:
        for attempt in range(MAX_ATTEMPTS):
            try:
                return _call(model, prompt)
            except errors.APIError as e:
                last_error = e
                if e.code not in RETRYABLE:
                    raise  # bad key, bad request, etc. -- retrying won't help
                print(f"[ai] {model} attempt {attempt + 1}/{MAX_ATTEMPTS}: {e.code} {e.status}, retrying...")
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e  # model returned bad JSON; try again
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BASE_DELAY_S * (2 ** attempt))
        print(f"[ai] {model} failed after {MAX_ATTEMPTS} attempts: {last_error}")

    raise AIUnavailable(str(last_error))


# ---------------------------------------------------------------- prompts

ANALYZE_PROMPT = """You are helping build a fire-safety research dashboard from NASA
microgravity combustion experiments. Use ONLY the experiment data below.
Do not invent numbers or outcomes. Do not overstate results: if the data says
"burn time 70 s", do not call it a complete burn. If something is not in the
data, say "not reported".

Experiment data:
{row}

Return JSON with exactly these keys:

- "summary": 2-3 plain-English sentences: what was tested, under what conditions,
  and what happened.

- "fire_safety_relevance": integer 1-10, using this scale so scores spread out:
    9-10: real cabin materials (fabrics, plastics) burning or failing to burn at
          21% oxygen or higher, or results directly about putting fires out
          (suppression) or detecting them
    6-8:  useful related evidence: materials at lower oxygen, small samples,
          liquid or gas fuels with a clear finding about flammability limits,
          extinction or suppression (e.g. CO2 or helium added)
    3-5:  mostly basic combustion science with only an indirect link to crew safety
    1-2:  little or no fire-safety value (e.g. outcome not reported)

- "relevance_reason": one sentence explaining the score.

- "environments": always include "spacecraft" and "space station" (all tests are
  in microgravity). Add "lunar base", "mars base" and "pressurized rover" ONLY if
  the oxygen is 25% or higher or pressure is below 12 psi (planned habitat
  atmospheres are lower pressure and higher oxygen). Add "earth" only if the result
  clearly matters for fire safety on Earth too.

- "category": exactly one of:
    "prevention"  - flammability / material / ignition tests
    "suppression" - extinguishment, diluent gases (CO2, helium), flame going out
    "detection"   - smoke, sensors, early warning
    "other"       - none of the above

- "key_findings": up to 3 short findings, each stated in the data above.
"""

RISK_PROMPT = """You are a fire-safety research assistant writing a short explanation
for a user. The risk level and the evidence were already decided by code from
NASA microgravity combustion data. Your job is ONLY to explain them in plain English.

Rules:
- Use ONLY the numbers that appear in the facts below. Do not calculate, convert,
  estimate or invent any number. If you mention a number, copy it exactly.
- Cite experiments by id, e.g. (PSI-99-2-8).
- Use the risk word "{risk_level}" and explain the reason given.
- Say clearly that the user's exact conditions have not been tested if the gaps say so.
- Higher oxygen generally increases flammability; you may say this in words.
- {gravity_note}
- Plain words only: no internal terms like "match distance".
- This is a research aid, not a safety certification.

User conditions:
{conditions}

Risk level (decided): {risk_level}
Reason: {reason}

Evidence (each line is exact, from the data):
{evidence}

Data gaps already shown to the user (do not repeat them):
{known_gaps}

Return JSON with exactly these keys:
- "explanation": 3-4 plain-English sentences
- "data_gaps": list of ADDITIONAL short gaps not already listed (usually empty)
"""

PLACEMENT_PROMPT = """You are a stowage-planning assistant for a crewed {destination}
surface mission. An engineer is placing one item in the spacecraft. Code has
ALREADY rated the fire risk of each location in each mission phase, using NASA
microgravity combustion data. Your job is ONLY to suggest fixes, chosen from
what is listed below, and explain them in plain English.

Rules:
- Never change a risk rating. Use the ratings below exactly as given.
- A location counts as safe only if it is acceptable in BOTH phases
  (cruise and surface). Never suggest a fix that helps one phase but
  leaves either phase high or insufficient data. Never claim a fix is proven safe.
- Fix types you may use:
    "move"          - move the item to a location from "Candidate locations"
                      (use its exact id). Never invent a location.
    "separate"      - keep it in place but add distance or a barrier from the
                      neighboring item named in the reason
    "contain"       - put it in a fire-resistant bag or container
    "swap_material" - replace one of the item's listed materials with a less
                      flammable one (name which listed material)
- For "move", prefer candidates with better crew access. The engineer makes the
  final choice; you only suggest.
- When explaining a flag, name the phase, the condition (e.g. higher oxygen during
  EVA prep) and any neighboring item that caused it.
- Use ONLY numbers that appear below. Copy them exactly; do not calculate,
  convert, estimate or invent numbers.
- Cite experiments only by the ids in the evidence list, e.g. (PSI-99-2-8).
- {gravity_note}
- Launch is out of scope; consider cruise and surface operations only.
- Plain words only: no internal terms like "match distance".
- This is a planning aid, not a safety certification; M&P and S&MA approve.

Item:
{item}

Mission conditions:
{conditions}

Current location: {current_id} ({current_module})
Nearby items at current location:
{neighbors}

Risk at current location (decided by code):
{current_ratings}
Overall (worse of the two phases): {current_overall}

Candidate locations (risk decided by code; best crew access first):
{candidates}

Evidence (each line is exact, from the data):
{evidence}

Data gaps already shown to the user (do not repeat them):
{known_gaps}

Return JSON with exactly these keys:
- "summary": 1-2 sentences. Say whether the current placement is acceptable in
  both phases; if not, name the phase, the condition and any neighboring item.
- "options": list of up to 4 fixes, best first (empty list if the current
  placement is already low in both phases). Each option is an object with:
    "type": one of "move", "separate", "contain", "swap_material"
    "location_id": the candidate id for "move", otherwise null
    "action": one short instruction an engineer or crew member could follow
    "why": one sentence saying which phase(s) it fixes and how
- "recommended": 0-based index of the best option in "options", or null if
  there are no options
- "data_gaps": list of ADDITIONAL short gaps not already listed (usually empty)
"""

# Fields the AI sees. source_quote / verified stay internal.
EXPERIMENT_FIELDS = [
    "id", "name", "investigation", "fuel_type", "material",
    "oxygen_pct_min", "oxygen_pct_max", "pressure_psi_min", "pressure_psi_max",
    "airflow_cm_s_min", "airflow_cm_s_max", "gravity",
    "outcome", "outcome_category", "description", "match_distance",
]


def _clean(d: Dict) -> Dict:
    """Keep only the fields the AI needs; turn NaN into None so JSON is valid."""
    out = {}
    for k in EXPERIMENT_FIELDS:
        if k in d:
            v = d[k]
            out[k] = None if (isinstance(v, float) and v != v) else v
    return out


def _gravity_note(conditions: Dict) -> str:
    gravity = float(conditions.get("gravity_g") or 0)
    if gravity > 0:
        return (f"The user's habitat has {gravity} g gravity, but all experiments are "
                "microgravity; there is no partial-gravity data (already listed in the gaps).")
    return "The user's habitat is in microgravity, like the experiments."


def analyze_experiment(row: Dict) -> dict:
    """Used by analyze.py: one experiment row -> summary/relevance JSON."""
    return ask_json(ANALYZE_PROMPT.format(row=json.dumps(_clean(row), indent=2, default=str)))


def assess(conditions: Dict, risk_level: str, reason: str,
           evidence_lines: List[str], known_gaps: Optional[List[str]] = None) -> dict:
    """Used by POST /assess: the code has already decided risk_level and evidence;
    the AI only writes the explanation (main.py checks its numbers)."""
    prompt = RISK_PROMPT.format(
        gravity_note=_gravity_note(conditions),
        conditions=json.dumps(conditions, indent=2),
        risk_level=risk_level,
        reason=reason,
        evidence="\n".join(f"- {line}" for line in evidence_lines) or "- (none)",
        known_gaps="\n".join(f"- {g}" for g in (known_gaps or [])) or "- (none)",
    )
    return ask_json(prompt)


# ---------------------------------------------------------------- placement

PHASES = ("cruise", "surface")
RISK_ORDER = {"low": 0, "elevated": 1, "high": 2}
FIX_TYPES = {"move", "separate", "contain", "swap_material"}
MAX_OPTIONS = 4


def _rank(risk: str) -> int:
    return RISK_ORDER.get(risk, 3)  # unknown is not evidence of high risk


def overall_risk(ratings: Dict[str, Dict]) -> str:
    """Overall rating = the worse of the two phases."""
    values = [(ratings.get(p) or {}).get("risk", "insufficient data") for p in PHASES]
    if "high" in values:
        return "high"
    if any(v not in RISK_ORDER for v in values):
        return "insufficient data"
    return max(values, key=_rank)


def _fmt_ratings(ratings: Dict[str, Dict]) -> str:
    return "\n".join(
        f"- {p}: {(ratings.get(p) or {}).get('risk', 'insufficient data')} "
        f"({(ratings.get(p) or {}).get('reason', 'phase data not reported')})"
        for p in PHASES)



def _usable_candidates(current: Dict, candidates: List[Dict]) -> List[Dict]:
    """Code decides which locations are allowed as a 'move' target:
    no worse than the current spot in either phase, and better overall
    (or Low in both). The AI never sees the others."""
    cur = current.get("ratings") or {}
    cur_overall = _rank(overall_risk(cur))
    keep = []
    for c in candidates:
        r = c.get("ratings") or {}
        if any((r.get(p) or {}).get("risk") not in RISK_ORDER for p in PHASES):
            continue
        if any(r[p]["risk"] == "high" for p in PHASES):
            continue
        if any(_rank(r[p]["risk"]) > _rank((cur.get(p) or {}).get("risk")) for p in PHASES):
            continue
        cand_overall = _rank(overall_risk(r))
        if cand_overall < cur_overall or cand_overall == RISK_ORDER["low"]:
            keep.append(c)
    # best crew access first (higher number = easier access)
    return sorted(keep, key=lambda c: -(c.get("crew_access") or 0))


def _fmt_candidates(cands: List[Dict]) -> str:
    if not cands:
        return "- (none: no location is safer in both phases; use separate/contain/swap_material)"
    lines = []
    for c in cands:
        r = c.get("ratings") or {}
        pre = " (pre-cleared)" if c.get("pre_cleared") else ""
        lines.append(f"- {c['id']} ({c.get('module', '?')}){pre}: "
                     f"cruise {r['cruise']['risk']}, surface {r['surface']['risk']}, "
                     f"crew access {c.get('crew_access', 'not reported')}")
    return "\n".join(lines)


def _placement_numbers_ok(text: str, source: str) -> bool:
    # Ignore numbers embedded in identifiers, but check distances and unitless claims too.
    pattern = r"(?<![\w.\-])[-+]?\d+(?:\.\d+)?(?![\w.\-])"
    allowed = {float(n) for n in re.findall(pattern, source)}
    return all(float(n) in allowed for n in re.findall(pattern, text))


def _validate_placement(result: Dict, allowed_ids: set, item_materials: List[str],
                        number_source: Optional[str] = None) -> Dict:
    """Throw away anything the AI made up: unknown fix types, moves to locations
    the code didn't allow, swaps of materials the item doesn't have."""
    result = result if isinstance(result, dict) else {}
    raw = result.get("options") or []
    options = []
    original_indexes = []
    for original_index, o in enumerate(raw if isinstance(raw, list) else []):
        if not isinstance(o, dict) or o.get("type") not in FIX_TYPES:
            continue
        if not all(isinstance(o.get(k), str) and o[k].strip() for k in ("action", "why")):
            continue
        if number_source is not None and not all(_placement_numbers_ok(o[k], number_source) for k in ("action", "why")):
            continue
        o = dict(o)
        if o["type"] == "move":
            if o.get("location_id") not in allowed_ids:
                continue
        else:
            o["location_id"] = None
        if o["type"] == "swap_material":
            text = f"{o.get('action', '')} {o.get('why', '')}".lower()
            if not any(m.lower() in text for m in item_materials):
                continue
        original_indexes.append(original_index)
        options.append({k: o.get(k) for k in ("type", "location_id", "action", "why")})
        if len(options) == MAX_OPTIONS:
            break

    rec = result.get("recommended")
    rec = original_indexes.index(rec) if type(rec) is int and rec in original_indexes else None
    summary = str(result.get("summary") or "").strip()
    if number_source is not None and not _placement_numbers_ok(summary, number_source):
        summary = "Placement requires review against the phase ratings and data gaps."
    raw_gaps = result.get("data_gaps") or []
    gaps = [g for g in raw_gaps if isinstance(g, str) and g.strip()
            and (number_source is None or _placement_numbers_ok(g, number_source))] if isinstance(raw_gaps, list) else []

    return {
        "summary": summary,
        "options": options,
        "recommended": rec,
        "data_gaps": gaps,
    }


def advise_placement(item: Dict, current: Dict, candidates: List[Dict], conditions: Dict,
                     evidence_lines: List[str], known_gaps: Optional[List[str]] = None,
                     destination: str = "lunar") -> dict:
    """Used by POST /placement. Code has already rated every location per phase;
    the AI picks and explains fixes. Returned options are validated here
    including number checks on summary/action/why and additional gaps.

    item       = {"name": str, "materials": [str], "notes": str?}
    current    = {"id", "module", "neighbors": [{"name", "hazard"}],
                  "ratings": {"cruise": {"risk", "reason"}, "surface": {"risk", "reason"}}}
    candidates = [{"id", "module", "crew_access": int?, "pre_cleared": bool?, "ratings": {...}}]
                 For the surface re-check (Isaac), pass only the pre-cleared locations.
    conditions = {"cruise": {...}, "surface": {..., "gravity_g": 0.16}}
    """
    usable = _usable_candidates(current, candidates)
    neighbors = current.get("neighbors") or []
    surface = conditions.get("surface") or {}

    prompt = PLACEMENT_PROMPT.format(
        destination=destination,
        gravity_note="Cruise is in microgravity, like the experiment dataset. Launch is out of scope. " + (_gravity_note(surface) if surface else "Surface conditions are not reported; do not assume microgravity."),
        item=json.dumps(item, indent=2),
        conditions=json.dumps(conditions, indent=2),
        current_id=current["id"],
        current_module=current.get("module", "?"),
        neighbors="\n".join(f"- {n['name']}: {n.get('hazard', 'not reported')}" for n in neighbors)
                  or "- (none)",
        current_ratings=_fmt_ratings(current.get("ratings") or {}),
        current_overall=overall_risk(current.get("ratings") or {}),
        candidates=_fmt_candidates(usable),
        evidence="\n".join(f"- {line}" for line in evidence_lines) or "- (none)",
        known_gaps="\n".join(f"- {g}" for g in (known_gaps or [])) or "- (none)",
    )
    result = _validate_placement(ask_json(prompt), {c["id"] for c in usable},
                                 item.get("materials") or [],
                                 json.dumps([item, current, usable, conditions, evidence_lines, known_gaps]))
    result["overall"] = overall_risk(current.get("ratings") or {})  # from code, not the AI
    return result


# ---------------------------------------------------------------- stowage planner (/api/assess, /api/chat)

PLANNER_TEXT_PROMPT = """You are the fire-safety agent inside a stowage planning tool used by NASA
stowage engineers. Code has ALREADY scored every space for two mission phases, in-space
cruise (0 g) and surface operations, from NASA microgravity combustion data. Your job is
ONLY to write short plain-English text about those results.

Rules:
- Never change, recalculate or invent a score, level or any other number. If you mention
  a number, copy it exactly from the facts below. Prefer words to numbers.
- Refer to spaces and items only by the exact names given.
- Explain WHY using the factors and items given (thin acrylic beside a 3D printer, an
  oxygen outlet next to foam, low airflow, an item with no NASA test data).
- In microgravity there is no buoyant convection: flames are slower, but smoke reaches
  detectors only through forced airflow, and loose soft goods drift.
- Say when a score is an estimate because an item has no NASA test data.
- {gravity_note}
- Launch is out of scope. This is a planning aid, not a safety certification.

Mission and scores (decided by code):
{facts}

Return JSON with exactly these keys:
- "summary": two plain sentences on the whole ship (which phase drives the overall and why)
- "rooms": {{"<space id>": "<rationale, max 18 words>"}} for every space listed under "rooms"
- "fixes": {{"<space id>": ["<why, max 14 words>", ...]}} one reason per fix listed for that
  space, in the same order
"""

PLANNER_CHAT_TABS = {
    "overall": "Overall fire risk",
    "factors": "Risk factors",
    "moves": "Suggested moves",
    "table": "Space by space",
}

PLANNER_CHAT_PROMPT = """You are the fire-safety agent in a NASA stowage planning tool. The user is on
the "{tab}" tab; keep answers focused on it. The two phases are in-space cruise (0 g) and
surface operations. Scores below were computed by code from NASA test data: never change
or invent a number, and copy any number you mention exactly. Be concise (under 110 words),
concrete, and refer to spaces and items by name. {gravity_note}

If you recommend changes, include them as actions using ids from the ship data:
  {{"type":"swap","room_id","item_id","to":"<the item's swap_to key>"}}
  {{"type":"add","room_id","key":"ext"|"det"}}
  {{"type":"move","item_id","from_id","to_id"}}  (never into a passage)

SHIP DATA:
{ship}

LATEST ASSESSMENT:
{result}

CONVERSATION SO FAR (oldest first):
{history}

Return ONLY JSON: {{"reply": "plain text", "actions": []}}
"""


def planner_text(facts: Dict, gravity_g: float = 0.0) -> dict:
    """Used by POST /api/assess. facts = scores, rooms and fixes from code (backend/api.py)."""
    prompt = PLANNER_TEXT_PROMPT.format(gravity_note=_gravity_note({"gravity_g": gravity_g}),
                                        facts=json.dumps(facts, indent=1))
    return ask_json(prompt)


def planner_chat(tab: str, history: List[Dict], ship: Dict, result: Dict, gravity_g: float = 0.0) -> dict:
    """Used by POST /api/chat. history = [{"role": "user"|"agent", "text", "actions"}], newest last."""
    lines = []
    for m in history:
        if m["role"] == "user":
            lines.append("USER: " + m["text"])
        else:
            lines.append("AGENT: " + json.dumps({"reply": m["text"], "actions": m.get("actions") or []}))
    prompt = PLANNER_CHAT_PROMPT.format(tab=PLANNER_CHAT_TABS.get(tab, tab),
                                        gravity_note=_gravity_note({"gravity_g": gravity_g}),
                                        ship=json.dumps(ship), result=json.dumps(result),
                                        history="\n".join(lines))
    return ask_json(prompt)
