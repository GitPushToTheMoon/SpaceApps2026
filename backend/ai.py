"""Every Gemini call lives here. The API key never leaves the backend.

Setup: pip install google-genai python-dotenv
Key + model come from .env: GEMINI_API_KEY, GEMINI_MODEL (e.g. a current "flash" model)
"""


def ask_json(prompt):
    # TODO: send a prompt to Gemini and return the parsed JSON response
    # - load the key from .env (python-dotenv)
    # - ask for JSON output (response_mime_type="application/json")
    # - low temperature (~0.2) for consistent answers
    # - raise a clear error if the response isn't valid JSON
    pass


# TODO: ANALYZE_PROMPT - used once per experiment by analyze.py
# Should tell Gemini to:
# - use ONLY the experiment data given, never invent numbers ("not reported" if missing)
# - return JSON with: summary, fire_safety_relevance (1-10), relevance_reason,
#   environments (from a fixed list), category (prevention/detection/suppression/other),
#   key_findings (up to 3)
ANALYZE_PROMPT = ""


# TODO: RISK_PROMPT - used live by POST /assess
# Should tell Gemini to:
# - base everything ONLY on the matched experiments, cite them by id
# - never invent numbers; if the data doesn't cover the conditions -> "insufficient data"
# - mention that there's no partial-gravity (Moon/Mars) data when relevant
# - say it's a research aid, not a safety certification
# - return JSON with: risk_level, explanation, evidence [{id, what_happened}], data_gaps
RISK_PROMPT = ""


def assess(conditions, matched_experiments):
    # TODO: fill RISK_PROMPT with the user's conditions + matched experiments
    #       (leave out source_quote/verified), call ask_json, return the dict
    pass
