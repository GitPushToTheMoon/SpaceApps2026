"""Every Gemini call lives here. Keys and credentials never leave the backend.

Settings (.env):
  GEMINI_MODEL           main model, e.g. gemini-2.5-flash
  GEMINI_FALLBACK_MODEL  optional backup model used if the main one is overloaded
  USE_VERTEX             "true" to use Vertex AI (Google Cloud credits), else AI Studio key
  GEMINI_API_KEY         AI Studio key (when USE_VERTEX is not true)
  GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, GOOGLE_APPLICATION_CREDENTIALS  (Vertex)
"""
import json
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


def analyze_experiment(row: Dict) -> dict:
    """Used by analyze.py: one experiment row -> summary/relevance JSON."""
    return ask_json(ANALYZE_PROMPT.format(row=json.dumps(_clean(row), indent=2, default=str)))


def assess(conditions: Dict, risk_level: str, reason: str,
           evidence_lines: List[str], known_gaps: Optional[List[str]] = None) -> dict:
    """Used by POST /assess: the code has already decided risk_level and evidence;
    the AI only writes the explanation (main.py checks its numbers)."""
    gravity = float(conditions.get("gravity_g") or 0)
    if gravity > 0:
        gravity_note = (f"The user's habitat has {gravity} g gravity, but all experiments are "
                        "microgravity; there is no partial-gravity data (already listed in the gaps).")
    else:
        gravity_note = "The user's habitat is in microgravity, like the experiments."

    prompt = RISK_PROMPT.format(
        gravity_note=gravity_note,
        conditions=json.dumps(conditions, indent=2),
        risk_level=risk_level,
        reason=reason,
        evidence="\n".join(f"- {line}" for line in evidence_lines) or "- (none)",
        known_gaps="\n".join(f"- {g}" for g in (known_gaps or [])) or "- (none)",
    )
    return ask_json(prompt)
