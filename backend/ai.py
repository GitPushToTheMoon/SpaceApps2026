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


def _call(model: str, prompt: str) -> dict:
    resp = client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    text = (resp.text or "").strip()
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
            except (json.JSONDecodeError, ValueError) as e:
                last_error = e  # model returned bad JSON; try again
            if attempt < MAX_ATTEMPTS - 1:
                time.sleep(BASE_DELAY_S * (2 ** attempt))
        print(f"[ai] {model} failed after {MAX_ATTEMPTS} attempts: {last_error}")

    raise AIUnavailable(f"Gemini unavailable: {last_error}")


# ---------------------------------------------------------------- prompts

ANALYZE_PROMPT = """You are helping build a fire-safety research dashboard from NASA
microgravity combustion experiments. Use ONLY the experiment data below.
Do not invent numbers. If something is not in the data, say "not reported".

Experiment data:
{row}

Return JSON with exactly these keys:
- "summary": 2-3 sentence plain-English summary of what was tested and what happened
- "fire_safety_relevance": integer 1-10 (how useful for fire safety in crewed habitats:
   spacecraft cabins, space stations, Moon/Mars habitats, pressurized rovers)
- "relevance_reason": one sentence explaining the score
- "environments": list chosen from ["spacecraft", "space station", "lunar base",
   "mars base", "pressurized rover", "earth"]
- "category": one of ["prevention", "detection", "suppression", "other"]
- "key_findings": list of up to 3 short findings, each grounded in the data above
"""

RISK_PROMPT = """You are a fire-safety research assistant. A user describes habitat
conditions. Below are the closest NASA microgravity combustion experiments
(selected by code, not by you).

Rules:
- Base everything ONLY on these experiments. Cite them by id, e.g. (PSI-69-019).
- Do not invent numbers or outcomes. If the experiments don't cover the user's
  conditions (oxygen, pressure, airflow or material), say so and use
  risk_level "insufficient data".
- Higher oxygen generally increases flammability; only claim this for the user's
  conditions if the cited experiments support it.
- {gravity_note}
- This is a research aid, not a safety certification.

User conditions:
{conditions}

Matching experiments (closest first; match_distance 0 = conditions fall inside that test's ranges):
{experiments}

Return JSON with exactly these keys:
- "risk_level": one of ["low", "elevated", "high", "insufficient data"]
- "explanation": 3-5 plain-English sentences citing experiment ids
- "evidence": list of {{"id": "<experiment id>", "what_happened": "<one sentence>"}}
- "data_gaps": list of short strings describing what the data does not cover
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


def assess(conditions: Dict, matched_experiments: List[Dict]) -> dict:
    """Used by POST /assess: user conditions + matched experiments -> risk JSON."""
    gravity = float(conditions.get("gravity_g") or 0)
    if gravity > 0:
        gravity_note = (
            f"The user's habitat has {gravity} g gravity. All experiments are microgravity; "
            "there is no partial-gravity combustion data yet. Say so in data_gaps."
        )
    else:
        gravity_note = "The user's habitat is in microgravity, like the experiments."

    prompt = RISK_PROMPT.format(
        gravity_note=gravity_note,
        conditions=json.dumps(conditions, indent=2),
        experiments=json.dumps([_clean(e) for e in matched_experiments], indent=2, default=str),
    )
    return ask_json(prompt)
