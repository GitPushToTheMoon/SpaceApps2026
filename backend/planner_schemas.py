"""Planner API contract: experiment evidence and prototype scores stay distinct."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, model_validator
from .schemas import Evidence, RiskLevel


class PlannerInput(BaseModel):
    model_config = {"allow_inf_nan": False}


class Dimensions(PlannerInput):
    l: float = Field(..., gt=0, le=10000)
    w: float = Field(..., gt=0, le=10000)
    h: float = Field(..., gt=0, le=10000)


class PlannerItem(PlannerInput):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    category: Literal["material", "machinery", "safety"] = "material"
    material_key: Optional[str] = None
    quantity: int = Field(1, ge=1, le=10000)
    dimensions_cm: Dimensions
    ignition_source: bool = False
    oxygen_source: bool = False
    bagged: bool = False
    loose_soft_goods: bool = False
    equipment: Optional[Literal["heater", "3d_printer", "li_ion", "pump", "exercise", "consoles", "laptop", "fan", "other", "extinguisher", "smoke_detector", "breathing_mask"]] = None


class Position(PlannerInput):
    x: int
    y: int


class PlannerSpace(PlannerInput):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    kind: Literal["room", "passage"] = "room"
    type: str = "Other"
    position: Optional[Position] = None
    airflow_cm_s: float = Field(..., ge=0, le=500)
    capacity_kg: Optional[float] = Field(None, gt=0)
    items: list[PlannerItem] = Field(default_factory=list, max_length=100)


class Atmosphere(PlannerInput):
    pressure_psia: float = Field(14.7, gt=0, le=50)
    o2_percent: float = Field(21, ge=0, le=100)


class PlannerScenario(PlannerInput):
    cruise_days: float = Field(180, gt=0, le=100000)
    surface_stay_days: float = Field(30, gt=0, le=100000)
    ventilation: Literal["normal", "reduced"] = "normal"
    cruise_atmosphere: Atmosphere = Field(default_factory=Atmosphere)
    cabin_atmosphere: Atmosphere = Field(default_factory=Atmosphere)


class PlannerRequest(PlannerInput):
    mission: Literal["cruise", "lunar", "mars"] = "cruise"
    scenario: PlannerScenario = Field(default_factory=PlannerScenario)
    spaces: list[PlannerSpace] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({s.id for s in self.spaces}) != len(self.spaces):
            raise ValueError("Space ids must be unique.")
        ids = [i.id for s in self.spaces for i in s.items]
        if len(set(ids)) != len(ids):
            raise ValueError("Item ids must be unique across the spacecraft.")
        positions = [(s.position.x, s.position.y) for s in self.spaces if s.position]
        if len(set(positions)) != len(positions):
            raise ValueError("Spaces cannot share a grid position.")
        return self


PlannerLevel = Literal["Low", "Guarded", "Elevated", "High", "Severe"]


class PlannerScore(BaseModel):
    score: Optional[float] = Field(None, ge=0, le=100)
    level: Optional[PlannerLevel] = None
    lower_bound: float = Field(..., ge=0, le=100)
    upper_bound: float = Field(..., ge=0, le=100)
    status: Literal["prototype", "insufficient data"]
    summary: str


class MaterialScreen(BaseModel):
    item_id: str
    material_key: Optional[str]
    risk_level: RiskLevel
    points: Optional[int] = None
    verified_tests: int
    evidence: list[Evidence]
    data_gaps: list[str]
    reason: str


class FactorRange(BaseModel):
    lower_bound: float = Field(..., ge=0, le=100)
    upper_bound: float = Field(..., ge=0, le=100)


class FactorSummary(FactorRange):
    min: float = Field(..., ge=0, le=100)
    max: float = Field(..., ge=0, le=100)


class PlannerRoom(BaseModel):
    id: str
    name: str
    scores: dict[str, PlannerScore]
    factors: dict[str, dict[str, FactorRange]]
    materials: dict[str, list[MaterialScreen]]


class PlannerAction(BaseModel):
    severity: Literal["review", "improvement"]
    space: str
    title: str
    item_id: Optional[str] = None
    target_space_id: Optional[str] = None
    combined_uncapped_before: Optional[float] = None
    combined_uncapped_after: Optional[float] = None
    reduction: Optional[float] = None


class PlannerResponse(BaseModel):
    phases: list[str]
    ship: dict[str, PlannerScore]
    overall: PlannerScore
    rooms: list[PlannerRoom]
    factors: dict[str, dict[str, FactorSummary]]
    actions: list[PlannerAction]
    hazards: list[str]
    model_info: dict
