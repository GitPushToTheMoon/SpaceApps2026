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
    "gravity_g": 0.166,
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
  "gravity_g": 0.166,
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

## Stowage Fire-Risk Planner: `GET /library`, `POST /api/assess`, `POST /api/chat`
Backend for the planner in the handoff README. **Every score, level, factor, fix and move
point comes from code** (`backend/scoring.py`, `backend/actions.py`). Gemini only writes the
summary, room rationales, fix reasons and chat replies, and every number it writes is checked
against the real values. Full request/response examples: `API_examples.json`.

### GET `/library`
The item list for the "Add to this space" dropdown (copied from the prototype's `BASE_LIB`):
`key`, `name`, `category` (material / machinery / safety), `flammability` (Low / Moderate / High
or null), `ignition_source`, `oxygen_source`, `swap` (lower-flammability key), `material_key`
(links to the NASA test data; null = no tests), `test_dataset` (PSI items), `default_cm` (safety).

### POST `/api/assess`
Request = the prototype's `agentInput()` JSON, **plus each item's library `key`**:
```json
{
  "conditions": {
    "cruise":  { "gravity_g": 0, "pressure_psia": 14.7, "o2_percent": 21, "ventilation": "normal", "cruise_days": 180 },
    "surface": { "body": "Moon", "gravity_g": 0.166, "pressure_psia": 10.2, "o2_percent": 30,
                 "stay_days": 30, "eva_prep_periods_high_o2": 4 }
  },
  "out_of_scope": ["launch"],
  "spaces": [{
    "id": "n3", "name": "Destiny Lab", "type": "Lab", "passage": false, "airflow_cm_s": 14,
    "capacity_kg": 70, "neighbours": ["n2", "n4"],
    "items": [{ "id": "n9", "key": "pmma", "name": "PMMA", "category": "material",
                "flammability": "High", "ignition_source": false, "oxygen_source": false,
                "qty": 3, "cm": [10, 8, 4] }]
  }]
}
```
- `surface: null` = cruise only. `ventilation: "reduced"` halves every space's cruise airflow.
- Extra fields (`baseline`, `swap_to`, `test_dataset`, `bagged`) are accepted and ignored or used.
- Space ids must be unique; `cm` needs 3 numbers. Bad input returns **422**.

Response (phases are `cruise` and `surf`, as in the handoff):
```json
{
  "overall": { "score": 60.2, "level": "High", "driver": "surf", "summary": "two sentences" },
  "phases":  { "cruise": { "score": 50.1, "level": "Elevated" }, "surf": { "score": 65.4, "level": "High" } },
  "rooms": [{
    "id": "n7", "name": "Quest Airlock", "stocked": true,
    "cruise": 51.3, "surf": 62.5, "overall": 58.7,
    "cruise_level": "Elevated", "surf_level": "High", "level": "Elevated",
    "rationale": "≤ 18 words",
    "fixes": [{ "title": "Swap Polyurethane foam for Melamine foam", "why": "≤ 14 words",
                "points": 23.7, "ship_points": 1.4,
                "action": { "type": "swap", "room_id": "n7", "item_id": "n6", "to": "melamine" } }],
    "factors": { "cruise": { "material": 50.0, "fuel": 14.3, "sources": 67.0, "airflow": 20.0, "thickness": 35.0 }, "surf": { } },
    "items": [{ "id": "n6", "name": "Polyurethane foam", "material_key": null,
                "hazard": { "cruise": 70.0, "surf": 95.0 }, "evidence": "none", "basis": "…" }]
  }],
  "factors": [{ "key": "material", "name": "Material hazard (NASA test data)", "weight": 0.45,
                "cruise": { "avg": 0, "min": 0, "max": 0 }, "surf": { "avg": 0, "min": 0, "max": 0 } }],
  "moves": [{ "item_id": "n6", "item": "Polyurethane foam", "qty": 1, "from_id": "n7", "from_name": "Quest Airlock",
              "to_id": "n2", "to_name": "PMM Stowage & Logistics", "reason": "…", "points": 2.2 }],
  "data_gaps": ["…"],
  "text_source": "ai",
  "input_hash": "a1b2c3d4e5f60718",
  "assessed_at": "2026-11-14T23:40:00+00:00",
  "disclaimer": "…"
}
```
**How the numbers are made (differs from the handoff's placeholder model):**
- Room score per phase = 0.45 material hazard + 0.20 fuel load + 0.15 ignition & oxygen sources
  (own room + neighbours) + 0.10 airflow + 0.10 thickness, −5 for a smoke detector, −5 for an
  extinguisher. Material hazard comes from the NASA burn / no-burn tests at that phase's oxygen.
- Ship phase = 0.6 × riskiest stocked space + 0.4 × average stocked space.
- **Overall = 0.6 × worse phase + 0.4 × day-weighted average** (not just the worse phase).
  The same formula gives each room's `overall`. `driver` = the phase with the higher score.
- **5 factors**, not 7: `material`, `fuel`, `sources`, `airflow`, `thickness`. Cabin pressure,
  EVA-prep periods, machinery heat and Li-ion bagging are not scored yet (listed in `data_gaps`).
- Empty spaces (nothing but safety gear) have `null` scores and no fixes.
- Fix `points` = real drop in that room's overall score; `ship_points` and move `points` = real
  drop in the ship's overall score. Code re-scores the ship with the change applied.
- Moves only go to non-passage spaces with no ignition or oxygen source.

**Frontend: show these numbers as they are; don't recompute scores, levels or points.**
Map colours can still use the 3 bands (Low ≤ 40, Elevated ≤ 60, High > 60) on these scores.

Always **200**: if Gemini is down or writes a wrong number twice, the text is plain template
text and `text_source` is `"template"`. Identical requests are cached; each assessment is
appended to `data/assessments.jsonl` (input + result, for M&P traceability).

### POST `/api/chat`
```json
{ "tab": "overall",
  "messages": [{ "role": "user", "text": "What single change lowers the score most?" }],
  "assessment_input": { "...": "same JSON as POST /api/assess" } }
```
- `tab`: `overall` | `factors` | `moves` | `table`. Keep one thread per tab and send the
  whole thread; agent turns go back as `{ "role": "agent", "text", "actions" }`.
  Only the last 10 messages are used.
- Response: `{ "reply": "…", "actions": [ { ...action, "label": "Swap X → Y", "points": 1.4 } ], "text_source": "ai" }`.
  Actions are checked against the ship (unknown ids, wrong swap, duplicate add, move into a
  passage are dropped) and `points` is the real drop in the ship's overall score.
- A reply with a wrong number is retried once, then replaced with a short "couldn't answer"
  message (`text_source: "fallback"`).
- **503** if Gemini is unreachable: show "The agent could not be reached. Try again in a moment."

### Applying an action (frontend)
| `type` | Fields | Change to the ship |
|---|---|---|
| `swap` | `room_id`, `item_id`, `to` | Replace that item's library key with `to` (keep qty and size) |
| `add` | `room_id`, `key` (`det` / `ext` / `mask`) | Add 1 of that library item, `default_cm` size |
| `move` | `item_id`, `from_id`, `to_id` | Move the item to the other space |

---

## POST `/admin/reload`
Backend team only: re-reads the CSVs and `analysis.json` after data updates and clears cached `/assess` answers.
If `ADMIN_TOKEN` is set on the server, send it as the `X-Admin-Token` header.

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
    "cruise": {"oxygen_pct": 21, "pressure_psi": 14.7, "airflow_cm_s": 10, "gravity_g": 0},
    "surface": {"oxygen_pct": 34, "pressure_psi": 8.2, "airflow_cm_s": 10, "gravity_g": 0.166}
  }
}
```
Missing or null phases return `insufficient data`; cruise gravity must be 0.
Materials must come from `/materials`. Each material is matched and rated with the
same rules as `/assess`. The phase rating is high if any material is high; otherwise
unknown evidence propagates as insufficient data; otherwise the worse known rating wins.
These are microgravity evidence screens: Surface gravity
remain unvalidated, with explicit data gaps. Neighbor and module hazards are
context for suggestions, not calculated risk modifiers.

Response fields: `overall`, `summary`, `options`, `recommended`, `locations`,
`evidence`, `data_gaps`, `disclaimer`. Each returned location includes
`ratings.cruise` and `ratings.surface` with `risk` and `reason`.
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
Errors: 400 unknown material/location, duplicate ids, or nonzero cruise gravity;
422 invalid request shape or out-of-range conditions. Never send API keys from the frontend.


## POST `/planner/assess` ? numeric stowage planner

Deterministic scoring; no Gemini call, key or network required. `/assess` and
`/placement` continue to return evidence ratings, not numeric planning scores.
The planning score is not a probability, NASA certification, or a calibrated
prediction. All layout weights and the evidence-to-points conversion are
prototype assumptions from the handoff; material evidence comes from verified CSV rows.

A complete runnable request is in `data/planner_example.json`. Minimal request:
```json
{
  "mission": "lunar",
  "scenario": {
    "cruise_days": 180,
    "surface_stay_days": 30,
    "ventilation": "normal",
    "cruise_atmosphere": {"pressure_psia": 14.7, "o2_percent": 21},
    "cabin_atmosphere": {"pressure_psia": 8.2, "o2_percent": 34}
  },
  "spaces": [{
    "id": "lab", "name": "Lab", "kind": "room", "type": "Lab",
    "position": {"x": 0, "y": 0}, "airflow_cm_s": 14,
    "items": [{
      "id": "panel", "name": "PMMA panel", "category": "material",
      "material_key": "PMMA", "quantity": 3,
      "dimensions_cm": {"l": 10, "w": 8, "h": 4}
    }]
  }]
}
```

`mission` is `cruise`, `lunar`, or `mars`; default cruise. Lunar/Mars include both
cruise and surface. Launch is excluded. Atmospheres default to 14.7 psia / 21%
oxygen for both phases; Mars does **not** silently assume exploration atmosphere.
Airflow is per space in cm/s. Dimensions are cm, not mm. Volume is converted to
litres: `l*w*h*quantity/1000`. Pressure uses psia, numerically equivalent to the
absolute psi values used by the experiment dataset. No automatic conversion of
gauge pressure or unlabelled dimensions from experiment descriptions is attempted.

Space and item ids must be unique (item ids across the whole ship). Grid positions
are optional, but missing positions produce a neighboring-hazard gap. Space `kind`
is `room` or `passage`. `capacity_kg` is metadata; item mass is not available and
capacity compliance is not calculated. Maximum 40 spaces and 100 items per space.
Dimensions must be positive, quantity a positive integer, airflow 0-500 cm/s,
oxygen 0-100%, pressure >0 to 50 psia, and phase durations positive. NaN/infinity
are rejected. Invalid input returns 422.

Items have category `material`, `machinery`, or `safety`; optional `material_key`,
`ignition_source`, `oxygen_source`, `bagged`, `loose_soft_goods` (booleans).
Recognized `equipment` values are `heater`, `3d_printer`, `li_ion`, `pump`,
`exercise`, `consoles`, `laptop`, `fan`, `other`, `extinguisher`, `smoke_detector`,
`breathing_mask`. Known heat equipment implies an ignition source. Use `other`
with `ignition_source` for other machinery. A machinery item contributes material
fuel only if a `material_key` is supplied; otherwise only its equipment hazards
are modeled. Model casing or other fuel with material items when needed.
Client `flammability` and `dataset_tests` metadata do not override CSV evidence.
Custom/missing material keys are accepted as **unknown**, to support saved items.

### Material evidence conversion

Only verified same-material rows are ranked by oxygen, pressure and airflow,
with the closest five used. No matches or no usable outcomes => `insufficient data`.
The existing evidence rules determine `high` (burning near/below requested oxygen),
`low` (non-burning evidence), or `elevated` (mixed/different conditions).
The planner tightens `low`: every selected test must have a known non-burning
outcome and cover all requested numeric conditions. Missing pressure/airflow
cannot support low. Gravity, specimen construction and thickness remain gaps.

Prototype conversion: `low -> 1`, `elevated -> 2`, `high -> 3` fuel points.
These points are an ordinal planning input, not a measured flammability property.
Unknown points span **1-3**. Score `score` and `level` are null if any material
is unknown; `lower_bound`/`upper_bound` show the prototype range instead.
Those bounds are not confidence intervals and do not bound unmodeled hazards.
Even if both bounds cap at 100, unknown evidence remains explicitly unknown.

### Score formulas and assumptions

Per item size factor is `min(4, 1+floor(total_litres/5))`. Fuel load sums material
points times size. Raw room points add 2 per ignition-source unit when fuel is
present, 4 for an oxygen source with moderate/high fuel, 2 for fuel in passages,
and subtract 1 each for detector/extinguisher presence. Room score is
`clamp(raw*7, 0, 100)`; empty rooms score zero and are excluded from ship averages.
Cruise adds up to 3 for loose-soft-goods units and 1 for missing detection.
Surface adds 2 for unbagged Li-ion, 1 for ignition with moderate/high fuel,
and Mars adds 1 for moderate/high fuel. Scenario adjustments follow the handoff:
cruise +2 reduced ventilation with ignition and no detector, +1 normal ventilation
with ignition and moderate/high fuel, +1 beyond 180 days, +1 low airflow with ignition;
surface +2 exploration oxygen with moderate/high fuel, +1 exploration oxygen with
oxygen source, +1 beyond 30 days with fuel load >=5. Exploration oxygen means >=34%.
Same-room means near; there is no within-room distance model.

Ship phase score = `0.6*max(stocked_room_scores) + 0.4*mean(stocked_room_scores)`.
Lunar/Mars overall = `0.6*max(cruise,surface) + 0.4*duration_weighted_mean`.
Cruise-only overall is cruise. Levels use continuous thresholds: <=20 Low,
<=40 Guarded, <=60 Elevated, <=80 High, otherwise Severe. Rounding is for display.

Seven separate factor bars are not summed into the room score:

| Key | Prototype calculation (clamped 0-100) |
|---|---|
| materials_fuel_load | fuel/14*100 + 5 per high item |
| oxygen_ventilation | 10 + 15 oxygen source + 40 near moderate/high fuel + 25 exploration oxygen + 10 reduced ventilation |
| cabin_pressure | 25 for 14.7/21; 70 for 8.2/34; otherwise unknown range 0-100 |
| airflow | under 5: 75-8*airflow; 5-15: 20; above 15: 20+6*(airflow-15) |
| material_thickness | minimum flammable item dimension: <0.5 =>85, <2 =>55, <5 =>35, else20; no moderate/high fuel =>0 |
| machinery_proximity | same space: 45+12 per ignition unit; neighboring ignition with moderate/high fuel:35; ignition only:20; else0 |
| machinery_heat | heater30, printer30, Li-ion25, pump20, exercise/consoles15, laptop10, fan5, other15, times quantity capped at3; +10 low airflow with ignition |

Minimum item dimension is a documented **thickness proxy**, not measured fabric
or wall thickness. Grid Manhattan distance 1 defines neighboring modules.
Room factor ranges propagate unknown material points; whole-ship factors return
mean lower/upper values and min/max across stocked spaces. Unsupported pressure
factor weights are left unknown instead of interpolated without evidence.

### Response and frontend integration

Top-level fields: `phases` (phase names), `ship` (phase -> score), `overall` (score),
`rooms`, `factors`, `actions`, `hazards`, `model_info`.
Every score object has `score`, `level`, `lower_bound`, `upper_bound`, `status`,
`summary`. Status is `prototype` or `insufficient data`. Room objects include
`id`, `name`, `scores` by phase, seven `factors` by phase, and `materials` by phase.
Each material screen has `risk_level`, `points`, `verified_tests`, exact experiment
`evidence` ids/sentences, `reason`, and `data_gaps`. These evidence labels retain
the `/assess` vocabulary; they are distinct from five-level planning labels.
`model_info` identifies version, prototype weights, conversion and assumptions.

Actions (up to five) prioritize unknown-material reviews, then independent item
moves with `item_id`, source `space`, `target_space_id`, uncapped before/after and
`reduction`, then missing-detector reviews. Move candidates are recomputed using
the destination airflow and must reduce the affected rooms' combined uncapped
mission score without worsening either phase's combined score. Moves are disabled
if any material is unknown. Re-run after applying each move; recommendations are
independent and are not a guaranteed optimal batch or safety approval.

The external canvas is not in this repository. Its frontend needs an adapter to
send this ship-level request (including stable ids) and render these typed response
objects. This endpoint is not a drop-in replacement for an undocumented `computeAI`
object or its per-phase request. Interactive schema: `/docs`.

Run the provided example from PowerShell while Uvicorn is running:
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/planner/assess -ContentType 'application/json' -Body (Get-Content data/planner_example.json -Raw)
```
