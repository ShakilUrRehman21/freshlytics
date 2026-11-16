from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    fruit_type: str
    freshness_stage: str
    freshness_score: int
    shelf_life_hours: float
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    confidence: Optional[float] = None
    rot_probability: Optional[float] = None
    storage_type: Optional[str] = None
    fruit_source: Optional[str] = None
    thumbnail: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        # SQLite returns naive UTC timestamps; make them explicit so browsers convert correctly
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v


class ScanDetail(ScanResponse):
    heatmap: Optional[str] = None


class ScanUpdate(BaseModel):
    notes: Optional[str] = None


class IdealConditions(BaseModel):
    temperature: str
    humidity: str


class PredictionResponse(BaseModel):
    scan_id: int
    created_at: datetime
    fruit: str
    fruit_source: str
    detected_fruit: str
    fruit_confidence: float
    fruit_uncertain: bool
    freshness_stage: str
    stage_description: str
    freshness_score: int
    rot_probability: float
    shelf_life_hours: float
    ai_confidence: float
    storage_type: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    recommendations: list[str]
    storage_recommendation: str
    ideal_conditions: IdealConditions
    thumbnail: str
    heatmap: str

    @field_validator("created_at")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v
