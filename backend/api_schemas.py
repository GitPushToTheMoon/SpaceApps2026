"""JSON contract for the Stowage Fire-Risk Planner: POST /api/assess and POST /api/chat.

The request is the planner prototype's agent input (handoff README, "Assessment call"),
plus each item's library `key`. Scores come from backend/scoring.py (code, from NASA test
data); Gemini only writes the summary, rationales and fix reasons.

Naming follows the handoff: "cruise" and "surf" are the two phases.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .schemas import DISCLAIMER

Level = Literal["Low", "Guarded", "Elevated", "High", "Severe"]
Phase = Literal["cruise", "surf"]


class In(BaseModel):
    """Request models: ignore extra fields the prototype sends (e.g. "baseline")."""
    model_config = {"extra": "ignore", "allow_inf_nan": False}


# ------------------------------------------------------------------ request

class CruiseConditions(In):
    gravity_g: float = Field(0, ge=0, le=0)
    pressure_psia: float = Field(14.7, gt=0, le=50)
    o2_percent: float = Field(21, ge=0, le=100)
    ventilation: Literal["normal", "reduced"] = "normal"
    cruise_days: float = Field(180, ge=0, le=100000)


class SurfaceConditions(In):
    body: Literal["Moon", "Mars"] = "Moon"
    gravity_g: float = Field(0.166, ge=0, le=1.5)
    pressure_psia: float = Field(10.2, gt=0, le=50)
    o2_percent: float = Field(26.5, ge=0, le=100)
    stay_days: float = Field(30, ge=0, le=100000)
    eva_prep_periods_high_o2: int = Field(0, ge=0, le=1000)


class Conditions(In):
    cruise: CruiseConditions = Field(default_factory=CruiseConditions)
    surface: Optional[SurfaceConditions] = Field(
        default_factory=SurfaceConditions, description="null = cruise only")


class PlannerItem(In):
    id: str = Field(..., min_length=1)
    key: Optional[str] = Field(None, description="Library key from GET /library, e.g. 'pmma', 'laptop'")
    name: str = Field(..., min_length=1)
    category: Literal["material", "machinery", "safety"] = "material"
    flammability: Optional[Literal["Low", "Moderate", "High"]] = None
    ignition_source: bool = False
    oxygen_source: bool = False
    qty: int = Field(1, ge=1, le=10000)
    cm: List[float] = Field(..., min_length=3, max_length=3, description="[L, W, H] in cm, all > 0")
    bagged: Optional[bool] = None
    swap_to: Optional[str] = None


class PlannerSpace(In):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str = "Other"
    passage: bool = False
    airflow_cm_s: float = Field(..., ge=0, le=500)
    capacity_kg: Optional[float] = Field(None, ge=0)
    neighbours: List[str] = Field(default_factory=list)
    items: List[PlannerItem] = Field(default_factory=list, max_length=200)


class AssessRequest(In):
    conditions: Conditions = Field(default_factory=Conditions)
    out_of_scope: List[str] = Field(default_factory=lambda: ["launch"])
    spaces: List[PlannerSpace] = Field(..., max_length=60)


# ------------------------------------------------------------------ actions

class Action(BaseModel):
    """swap: room_id, item_id, to | add: room_id, key | move: item_id, from_id, to_id"""
    type: Literal["swap", "add", "move"]
    room_id: Optional[str] = None
    item_id: Optional[str] = None
    to: Optional[str] = None
    key: Optional[str] = None
    from_id: Optional[str] = None
    to_id: Optional[str] = None


# ------------------------------------------------------------------ response

class PhaseScore(BaseModel):
    score: float = Field(..., ge=0, le=100)
    level: Level


class Overall(PhaseScore):
    driver: Phase = Field(..., description="The phase with the worse score ('DRIVES OVERALL')")
    summary: str = Field(..., description="Two plain sentences")


class Fix(BaseModel):
    title: str
    why: str
    points: float = Field(..., description="How much this room's score drops (re-scored by code)")
    ship_points: float = Field(..., description="How much the ship's overall score drops")
    action: Optional[Action] = None


class ItemEvidence(BaseModel):
    id: str
    name: str
    material_key: Optional[str] = None
    hazard: Dict[Phase, float] = Field(..., description="Material hazard 0-100 per phase")
    evidence: Literal["strong", "limited", "none"]
    basis: str
    n_tests: int = Field(0, description="Verified NASA tests of this material in our dataset")
    threshold_pct: Optional[float] = Field(None, description="Burn threshold (% oxygen) from the tests")
    gap: Optional[str] = None


class Room(BaseModel):
    id: str
    name: str
    stocked: bool
    cruise: Optional[float] = Field(None, description="null for an empty space")
    surf: Optional[float] = None
    overall: Optional[float] = None
    cruise_level: Optional[Level] = None
    surf_level: Optional[Level] = None
    level: Optional[Level] = None
    rationale: str = ""
    fixes: List[Fix] = Field(default_factory=list)
    factors: Dict[Phase, Dict[str, float]] = Field(default_factory=dict)
    items: List[ItemEvidence] = Field(default_factory=list)


class Band(BaseModel):
    avg: float
    min: float
    max: float


class Factor(BaseModel):
    key: str
    name: str
    weight: float
    cruise: Band
    surf: Optional[Band] = None


class Move(BaseModel):
    item_id: str
    item: str
    qty: int
    from_id: str
    from_name: str
    to_id: str
    to_name: str
    reason: str
    points: float = Field(..., description="How much the ship's overall score drops")


class AssessResponse(BaseModel):
    overall: Overall
    phases: Dict[Phase, PhaseScore]
    rooms: List[Room]
    factors: List[Factor]
    moves: List[Move]
    data_gaps: List[str]
    text_source: Literal["ai", "template"]
    input_hash: str
    assessed_at: str
    disclaimer: str = DISCLAIMER


# ------------------------------------------------------------------ chat

class ChatMessage(In):
    role: Literal["user", "agent"]
    text: str = Field(..., max_length=4000)
    actions: List[Action] = Field(default_factory=list)


class ChatRequest(In):
    tab: Literal["overall", "factors", "moves", "table"] = "overall"
    messages: List[ChatMessage] = Field(..., min_length=1, max_length=100)
    assessment_input: AssessRequest


class ChatAction(Action):
    label: str
    points: float = Field(..., description="How much the ship's overall score would drop")


class Citation(BaseModel):
    id: str = Field(..., description="Experiment id from experiments.csv, e.g. PSI-99-2-9")
    material: str
    investigation: str
    source_url: str


class ChatResponse(BaseModel):
    reply: str
    actions: List[ChatAction]
    citations: List[Citation] = Field(default_factory=list,
                                      description="Experiments the reply cites, with their NASA PSI source")
    text_source: Literal["ai", "fallback"]
