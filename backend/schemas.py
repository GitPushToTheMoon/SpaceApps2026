"""JSON shapes for the API. This file is the contract with the frontend.

Use Pydantic models (class X(BaseModel)) so FastAPI validates input and
documents everything automatically at /docs.
update API.md and tell the frontend team if changes made
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

FuelType = Literal["solid", "liquid", "gas"]
RiskLevel = Literal["low", "elevated", "high", "insufficient data"]
OutcomeCategory = Literal[
    "burned", "self-extinguished", "blowoff", "no ignition",
    "no spread", "ignited", "other", "unknown",
]
Environment = Literal[
    "spacecraft", "space station", "lunar base", "mars base", "pressurized rover", "earth",
]
Category = Literal["prevention", "detection", "suppression", "other"]

DISCLAIMER = "Research aid based on NASA microgravity experiments. Not a safety certification."


# ------------------------------------------------------------------ building blocks

class Range(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None


class PresetValue(BaseModel):
    default: float
    min: float
    max: float


class Source(BaseModel):
    title: str
    url: str


# ------------------------------------------------------------------ GET /materials

class Material(BaseModel):
    material: str = Field(..., description="Exact key the frontend sends back, e.g. 'PMMA'")
    display_name: str = Field(..., description="What users see, e.g. 'Acrylic plastic (PMMA)'")
    fuel_type: FuelType
    description: str = ""
    investigations: List[str] = []
    priority: int = Field(..., description="1 = most relevant to cabin fire safety")


# ------------------------------------------------------------------ GET /presets

class Preset(BaseModel):
    id: str = Field(..., examples=["moon_habitat"])
    display_name: str
    description: str
    pressure_psi: PresetValue
    oxygen_pct: PresetValue
    airflow_cm_s: PresetValue
    temperature_c: PresetValue = Field(..., description="Display only; not used in matching")
    gravity_g: float = Field(..., description="0 = microgravity, 0.165 = Moon, 0.38 = Mars")
    sources: List[Source] = []


# ------------------------------------------------------------------ GET /experiments

class Analysis(BaseModel):
    """AI-generated ahead of time by analyze.py."""
    summary: str = ""
    fire_safety_relevance: Optional[int] = Field(None, ge=1, le=10)
    relevance_reason: str = ""
    environments: List[str] = []
    category: Optional[str] = None
    key_findings: List[str] = []


class Experiment(BaseModel):
    id: str = Field(..., examples=["PSI-69-019"])
    name: str
    investigation: str
    fuel_type: Optional[FuelType] = None
    material: Optional[str] = None
    oxygen_pct: Range
    pressure_psi: Range
    airflow_cm_s: Range
    gravity: Optional[str] = None
    outcome: Optional[str] = Field(None, description="Original wording from the source")
    outcome_category: Optional[OutcomeCategory] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    analysis: Optional[Analysis] = Field(None, description="null until analyze.py has run for it")


class MatchedExperiment(Experiment):
    match_distance: float = Field(..., description="0 = user's conditions fall inside this test's ranges")


# ------------------------------------------------------------------ POST /assess

class AssessRequest(BaseModel):
    oxygen_pct: float = Field(..., ge=0, le=100, examples=[34])
    pressure_psi: float = Field(..., gt=0, le=50, examples=[8.2])
    airflow_cm_s: float = Field(..., ge=0, le=500, examples=[10])
    material: Optional[str] = Field(None, examples=["PMMA"], description="Key from /materials, or null for any")
    gravity_g: float = Field(0, ge=0, le=1.5, examples=[0.165], description="From the chosen preset")
    preset_id: Optional[str] = Field(None, examples=["moon_habitat"], description="Informational only")


class Evidence(BaseModel):
    id: str
    what_happened: str


class AssessResponse(BaseModel):
    risk_level: RiskLevel
    explanation: str
    evidence: List[Evidence] = []
    data_gaps: List[str] = []
    matches: List[MatchedExperiment] = []
    disclaimer: str = DISCLAIMER


# ------------------------------------------------------------------ GET /health, errors

class Health(BaseModel):
    status: Literal["ok", "error"]
    experiments: int


class ErrorResponse(BaseModel):
    """FastAPI's default error shape: {"detail": "..."}"""
    detail: str


# Placement ratings are microgravity evidence screens, not gravity validation.
class PlacementConditions(BaseModel):
    oxygen_pct: float = Field(..., ge=0, le=100, allow_inf_nan=False)
    pressure_psi: float = Field(..., gt=0, le=50, allow_inf_nan=False)
    airflow_cm_s: float = Field(..., ge=0, le=500, allow_inf_nan=False)
    gravity_g: float = Field(..., ge=0, le=1.5, allow_inf_nan=False)


class PlacementPhases(BaseModel):
    model_config = {"extra": "forbid"}
    cruise: Optional[PlacementConditions] = None
    surface: Optional[PlacementConditions] = None


class PlacementNeighbor(BaseModel):
    name: str
    hazard: str = "not reported"


class PlacementLocation(BaseModel):
    id: str
    module: str
    crew_access: int = Field(..., ge=0, le=5)
    pre_cleared: bool = False
    neighbors: List[PlacementNeighbor] = Field(default_factory=list)
    conditions: PlacementPhases = Field(default_factory=PlacementPhases)


class PlacementItem(BaseModel):
    name: str = Field(..., min_length=1)
    materials: List[str] = Field(..., min_length=1)
    notes: str = ""


class PlacementRequest(BaseModel):
    item: PlacementItem
    current_location_id: str
    destination: Literal["lunar", "mars"] = "lunar"
    locations: Optional[List[PlacementLocation]] = Field(None, min_length=1)
    pre_cleared_only: bool = False


class PlacementRating(BaseModel):
    risk: RiskLevel
    reason: str


class RatedPlacementLocation(PlacementLocation):
    ratings: dict[str, PlacementRating]


class PlacementOption(BaseModel):
    type: Literal["move", "separate", "contain", "swap_material"]
    location_id: Optional[str] = None
    action: str
    why: str


class PlacementResponse(BaseModel):
    overall: RiskLevel
    summary: str
    options: List[PlacementOption]
    recommended: Optional[int] = None
    locations: List[RatedPlacementLocation]
    evidence: List[Evidence]
    data_gaps: List[str]
    disclaimer: str = DISCLAIMER


# ================================================================== stowage planner
# POST /stowage/assess. Request follows the Stowage Fire-Risk Planner prototype's JSON.
# Scores are computed by backend/scoring.py (code); the AI only writes the text.

StowageLevel = Literal["Low", "Guarded", "Elevated", "High", "Severe"]
EvidenceLevel = Literal["strong", "limited", "none"]


class StowageDimensions(BaseModel):
    l: Optional[float] = Field(None, ge=0)
    w: Optional[float] = Field(None, ge=0)
    h: Optional[float] = Field(None, ge=0)


class StowageItem(BaseModel):
    name: str
    material_key: Optional[str] = Field(None, description="Key from /materials, or null if untested")
    category: Literal["material", "machinery", "safety"] = "material"
    flammability: Optional[Literal["Low", "Moderate", "High"]] = Field(
        None, description="Prototype's level; only used when the material has no test data")
    ignition_source: bool = False
    oxygen_source: bool = False
    quantity: int = Field(1, ge=1, le=1000)
    dimensions_cm: Optional[StowageDimensions] = None


class StowagePosition(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None


class StowageSpace(BaseModel):
    name: str
    kind: Optional[Literal["room", "passage"]] = "room"
    type: Optional[str] = None
    position: Optional[StowagePosition] = None
    airflow_cm_s: Optional[float] = Field(None, ge=0, le=500)
    capacity_kg: Optional[float] = Field(None, ge=0)
    items: List[StowageItem] = []


class CabinAtmosphere(BaseModel):
    pressure_psia: float = Field(..., gt=0, le=50)
    o2_percent: float = Field(..., ge=0, le=100)


class StowageScenario(BaseModel):
    destination: Literal["cruise_only", "moon", "mars"] = "moon"
    cruise_days: float = Field(180, ge=0, le=5000)
    surface_days: float = Field(30, ge=0, le=5000)
    cruise_atmosphere: CabinAtmosphere = CabinAtmosphere(pressure_psia=14.7, o2_percent=21)
    surface_atmosphere: CabinAtmosphere = Field(
        CabinAtmosphere(pressure_psia=8.2, o2_percent=34),
        description="Default = exploration atmosphere (same as the Moon/Mars presets)")
    cruise_ventilation: Literal["normal", "reduced"] = Field(
        "normal", description="'reduced' halves every space's airflow during cruise")


class StowageRequest(BaseModel):
    scenario: StowageScenario = StowageScenario()
    spaces: List[StowageSpace] = Field(..., min_length=1)


class StowageScore(BaseModel):
    score: float = Field(..., ge=0, le=100)
    level: StowageLevel


class StowagePhase(StowageScore):
    summary: str = ""


class StowageItemResult(BaseModel):
    name: Optional[str] = None
    material_key: Optional[str] = None
    hazard: float
    evidence: EvidenceLevel
    basis: str


class StowageRoomPhase(StowageScore):
    factors: Dict[str, float] = {}
    items: List[StowageItemResult] = []
    gaps: List[str] = []


class StowageRoom(BaseModel):
    name: str
    stocked: bool
    phases: Dict[str, StowageRoomPhase] = Field(..., description='keys: "cruise", and "surface" unless cruise_only')
    rationale: str = ""


class StowageAction(BaseModel):
    severity: Literal["high", "medium", "low"]
    room: Optional[str] = None
    title: str


class StowageResponse(BaseModel):
    overall: StowageScore
    phases: Dict[str, StowagePhase]
    rooms: List[StowageRoom]
    actions: List[StowageAction] = []
    hazards: List[str] = []
    data_gaps: List[str] = []
    text_source: Literal["ai", "template"] = Field(
        "ai", description="'template' when Gemini was unavailable or its text failed the number check")
    disclaimer: str = "Planning aid based on NASA microgravity experiments. Not a safety certification."
