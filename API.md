# Flame in Freefall API — JSON contract

Base URL (local): `http://localhost:8000`
Live interactive docs: `http://localhost:8000/docs` — try every endpoint in the browser.

All responses are JSON. Full example payloads built from real data: `API_examples.json`. Missing values are `null`, never empty strings or `NaN`.

---

## GET `/health`
Check the backend is up.
```json
{ "status": "ok", "experiments": 339 }
```

---

## GET `/materials`
For the material dropdown. Sorted by priority, then name.
Show `display_name` to users; send `material` back to the API.
```json
[
  {
    "material": "PMMA",
    "display_name": "Acrylic plastic (PMMA)",
    "fuel_type": "solid",
    "description": "Polymethyl methacrylate sheets, rods and structured samples",
    "investigations": ["BASS-II", "Saffire II", "Saffire IV", "Saffire V", "Saffire VI"],
    "priority": 1
  }
]
```

---

## GET `/presets`
Habitat presets for buttons. Clicking one should fill the sliders with each `default`;
`min`/`max` are the realistic range for that habitat.
```json
[
  {
    "id": "moon_habitat",
    "display_name": "Moon habitat (exploration atmosphere)",
    "description": "Lower pressure and higher oxygen so crews can suit up quickly for moonwalks.",
    "pressure_psi":  { "default": 8.2, "min": 8.2, "max": 8.2 },
    "oxygen_pct":    { "default": 34,  "min": 34,  "max": 34 },
    "airflow_cm_s":  { "default": 10,  "min": 5,   "max": 20 },
    "temperature_c": { "default": 22,  "min": 18,  "max": 27 },
    "gravity_g": 0.165,
    "sources": [ { "title": "…", "url": "…" } ]
  }
]
```
- Presets: `iss_cabin`, `moon_habitat`, `mars_habitat`.
- **Temperature is display-only** (cabin context). It is not sent to `/assess`: no
  experiment data includes temperature.
- Send the preset's `gravity_g` with `/assess`. For Moon/Mars the response always includes
  a "no partial-gravity data" item in `data_gaps`.

---

## GET `/experiments`
All verified experiments, sorted by AI relevance (highest first).

Optional query filters (combine freely):
| param | example |
|---|---|
| `investigation` | `?investigation=BASS-II` |
| `material` | `?material=PMMA` |
| `fuel_type` | `?fuel_type=solid` |
| `environment` | `?environment=lunar%20base` |
| `sort` | `relevance` (default) or `id` |

```json
[
  {
    "id": "SAFFIRE6-03",
    "name": "PMMA 1 cm, 2-sided",
    "investigation": "Saffire VI",
    "fuel_type": "solid",
    "material": "PMMA",
    "oxygen_pct":   { "min": 21.0, "max": 21.0 },
    "pressure_psi": { "min": 14.7, "max": 14.7 },
    "airflow_cm_s": { "min": 5.0,  "max": 20.0 },
    "gravity": "microgravity",
    "outcome": "…",
    "outcome_category": "self-extinguished",
    "description": "…",
    "source_url": "https://ntrs.nasa.gov/…",
    "analysis": {
      "summary": "…",
      "fire_safety_relevance": 8,
      "relevance_reason": "…",
      "environments": ["spacecraft", "lunar base"],
      "category": "prevention",
      "key_findings": ["…", "…"]
    }
  }
]
```
`analysis` can be `null` for experiments not analyzed yet — handle that.
`outcome_category` is one of: `burned`, `self-extinguished`, `blowoff`, `no ignition`,
`no spread`, `ignited`, `other`, `unknown` (use it for colors/filters; `outcome` is the source's wording).
Any `min`/`max` can be `null` if the source didn't report it.

## GET `/experiments/{id}`
One experiment, same shape as above. `404` if not found.

---

## POST `/assess`
The risk checker. Takes a few seconds (live AI call). Show a loading state.

Request:
```json
{
  "oxygen_pct": 30,
  "pressure_psi": 10.2,
  "airflow_cm_s": 10,
  "material": "PMMA",
  "gravity_g": 0.165,
  "preset_id": "moon_habitat"
}
```
`material` is optional (`null` = any material). Must be a `material` key from `/materials`.
`gravity_g` is optional (default 0 = microgravity). `preset_id` is optional; if the user moved
the sliders after picking a preset, still send the slider values, those are what count.

Response:
```json
{
  "risk_level": "elevated",
  "explanation": "3-5 sentences citing experiment ids…",
  "evidence": [
    { "id": "SAFFIRE6-03", "what_happened": "…" }
  ],
  "data_gaps": ["No tests above 26% oxygen for PMMA"],
  "matches": [ { "...same fields as an experiment...": "", "match_distance": 0.5 } ],
  "disclaimer": "Research aid based on NASA microgravity experiments. Not a safety certification."
}
```
- `risk_level` is always one of: `"low"`, `"elevated"`, `"high"`, `"insufficient data"`.
- `matches` = the 5 closest experiments, closest first. `match_distance` 0 = user's
  conditions fall inside that test's ranges; bigger = further away.
- Every `evidence[].id` is guaranteed to be one of the `matches`.

Errors:
| code | meaning | show the user |
|---|---|---|
| 400 | unknown material | "Pick a material from the list" |
| 422 | invalid input (e.g. oxygen > 100) | highlight the field |
| 502 | AI busy or failed (after retries + backup model) | "Assessment unavailable, try again" (a retry calls Gemini again) |

---

## POST `/stowage/assess`
Fire-risk score for a whole ship layout (Talia's Stowage Planner), for the cruise phase and,
for Moon/Mars, the surface phase. **Scores, levels and room order come from code**
(`backend/scoring.py`); Gemini only writes the summaries, room rationales, actions and
hazards, and every number in that text is checked against the real scores. If the text
fails the check twice, or Gemini is down, the endpoint still returns **200** with plain
template text and `"text_source": "template"`.

Request (only `spaces` is required; `scenario` has defaults):
```json
{
  "scenario": {
    "destination": "moon",              // "cruise_only" | "moon" | "mars"
    "cruise_days": 180, "surface_days": 30,
    "cruise_atmosphere":  { "pressure_psi": 14.7, "oxygen_pct": 21 },
    "surface_atmosphere": { "pressure_psi": 8.2,  "oxygen_pct": 34 },
    "cruise_ventilation": "normal"      // "reduced" halves cruise airflow
  },
  "spaces": [
    { "name": "PMM Stowage", "type": "Stowage", "position": {"x": 2, "y": 0},
      "airflow_cm_s": 3,
      "items": [
        { "name": "Cotton towels", "material_key": "cotton fabric", "flammability": "High",
          "quantity": 10, "dimensions_cm": {"l": 50, "w": 30, "h": 1} },
        { "name": "Laptop", "category": "machinery", "ignition_source": true },
        { "name": "Smoke detector", "category": "safety" }
      ] }
  ]
}
```
- `material_key` should be a `material` from `GET /materials`; unknown materials fall back
  to the `flammability` hint (Low/Medium/High) and get `"evidence": "none"`.
- `kind: "passage"` spaces (hatches, nodes) are only used for neighbour adjacency.
- Grid neighbours (`position` differs by 1) share ignition sources.

Response (full example in `API_examples.json`):
```json
{
  "overall": { "score": 66.5, "level": "High" },
  "phases": {
    "cruise":  { "score": 56.8, "level": "Elevated", "summary": "…" },
    "surface": { "score": 71.6, "level": "High",     "summary": "…" }
  },
  "rooms": [ { "name": "PMM Stowage", "stocked": true,
               "phases": { "cruise": { "score": 67.3, "level": "High", "items": [ … ] }, … },
               "rationale": "…" } ],
  "actions": [ { "severity": "high", "room": "PMM Stowage", "title": "…" } ],
  "hazards": [ "…" ],
  "data_gaps": [ "…" ],
  "text_source": "ai",                  // or "template"
  "disclaimer": "…"
}
```
- Levels: Low ≤20, Guarded ≤40, Elevated ≤60, High ≤80, Severe ≤100.
- Overall = 0.6 × worst phase + 0.4 × day-weighted average of phases.
- Bad input (no spaces, negative days, etc.) returns **422**.

---

## POST `/admin/reload`
Backend team only: re-reads the CSVs and `analysis.json` after data updates and clears cached `/assess` answers.
If `ADMIN_TOKEN` is set on the server, send it as the `X-Admin-Token` header.

---

## Rules for both teams
- **Frontend never talks to Gemini directly.** The API key lives only in the backend.
- **Changing a field name?** Update `backend/schemas.py` AND this file, and tell the other team.
- Frontend can build against the example JSON above before the backend is deployed.
