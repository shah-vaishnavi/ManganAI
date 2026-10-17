from typing import Dict, Optional
from pydantic import BaseModel, Field


class FeaturesIn(BaseModel):
    features: Dict[str, float] = Field(default_factory=dict)


class ReserveExplainIn(BaseModel):
    sample_id: Optional[str] = Field(None, max_length=32)
    features: Dict[str, float] = Field(default_factory=dict)


class ReservePredictIn(BaseModel):
    features: Dict[str, float | str] = Field(default_factory=dict)


class ScenarioIn(BaseModel):
    equipment_downtime: Optional[float] = Field(None, ge=0, le=24)
    equipment_availability: Optional[float] = Field(None, ge=0, le=1)
    rainfall: Optional[float] = Field(None, ge=0, le=500)
    weather_factor: Optional[float] = Field(None, ge=0, le=1.5)
    blasting_delay: Optional[float] = Field(None, ge=0, le=24)
    working_days: Optional[float] = Field(None, ge=0, le=7)


class ScenarioSaveIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    inputs: dict
    results: dict


class RefreshIn(BaseModel):
    seed: Optional[int] = None
    retrain: bool = False
