# Flame in Freefall API — JSON contract

Base URL (local): `http://localhost:8000`
Live interactive docs: `http://localhost:8000/docs` — try every endpoint in the browser.

All responses are JSON. Missing values are `null`, never empty strings or `NaN`.

---

## GET `/health`
Check the backend is up.
```json
{ "status": "ok", "experiments": 24 }
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
  "material": "PMMA"
}
```
`material` is optional (`null` = any material). Must be a `material` key from `/materials`.

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
| 502 | AI call failed | "Assessment unavailable, try again" — still show `matches` if you fetched them some other way |

---

## POST `/admin/reload`
Backend team only: re-reads the CSVs and `analysis.json` after data updates.

---

## Rules for both teams
- **Frontend never talks to Gemini directly.** The API key lives only in the backend.
- **Changing a field name?** Update `backend/schemas.py` AND this file, and tell the other team.
- Frontend can build against the example JSON above before the backend is deployed.


## GET `/locations`
Returns `data/locations.json`, currently **synthetic demo data**, not a mission layout.
Each location has `id`, `module`, `crew_access` (0-5, higher means easier access),
`pre_cleared`, `neighbors` (`name`, `hazard`) and `conditions` by phase.
Replace the file or provide `locations` in the placement request with engineer-supplied data.

## POST `/placement`
Example request using demo locations:
```json
{
  "item": {"name": "Panel", "materials": ["PMMA"], "notes": ""},
  "current_location_id": "demo_cabin",
  "destination": "lunar",
  "pre_cleared_only": false
}
```
Optional `locations` overrides the file. A location example:
```json
{
  "id": "custom_locker",
  "module": "Cabin",
  "crew_access": 3,
  "pre_cleared": false,
  "neighbors": [{"name": "Battery", "hazard": "Potential ignition source"}],
  "conditions": {
    "pre_launch": {"oxygen_pct": 21, "pressure_psi": 14.7, "airflow_cm_s": 10, "gravity_g": 1},
    "surface": {"oxygen_pct": 34, "pressure_psi": 8.2, "airflow_cm_s": 10, "gravity_g": 0.165}
  }
}
```
Missing or null phases return `insufficient data`; pre-launch gravity must be 1.
Materials must come from `/materials`. Each material is matched and rated with the
same rules as `/assess`. The phase rating is high if any material is high; otherwise
unknown evidence propagates as insufficient data; otherwise the worse known rating wins.
These are microgravity evidence screens: Earth pre-launch and surface gravity
remain unvalidated, with explicit data gaps. Neighbor and module hazards are
context for suggestions, not calculated risk modifiers.

Response fields: `overall`, `summary`, `options`, `recommended`, `locations`,
`evidence`, `data_gaps`, `disclaimer`. Each returned location includes
`ratings.pre_launch` and `ratings.surface` with `risk` and `reason`.
Ratings use `low / elevated / high / insufficient data` throughout.
Options contain `type` (`move / separate / contain / swap_material`),
`location_id` (only for moves), `action`, `why`. `recommended` indexes the
**filtered returned options**, or is null when its original option was rejected.
Moves exclude unknown or high phase ratings and must improve the overall screen
(or be low in both phases), without worsening either phase. These criteria do
not certify safety. `pre_cleared_only` restricts move candidates to pre-cleared locations.
AI text is checked for unsupported numeric values; invalid options/gaps are dropped,
and an invalid summary is replaced. This is a value check, not a guarantee that
units, causal claims or mitigation effectiveness are correct. Engineering approval is required.
If Gemini fails, ratings and evidence still return with empty options and an explicit gap.
Errors: 400 unknown material/location, duplicate ids, or non-Earth pre-launch gravity;
422 invalid request shape or out-of-range conditions. Never send API keys from the frontend.
