import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from alphaview_common.contracts import SOURCES
from alphaview_common.geo import GeoIn
from alphaview_common.research import ResearchOptions


class DiscoveryCreate(BaseModel):
    query: str = Field(min_length=2, max_length=300)
    sources: list[str] = Field(default_factory=lambda: [source for source in SOURCES if source != "web"])
    location: GeoIn | None = None
    research: ResearchOptions = Field(default_factory=ResearchOptions)


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    title: str
    cluster_label: str
    keywords: list[str]
    gap_score: float
    confidence: float
    metrics: dict[str, Any]
    evidence: list[dict[str, Any]]
    strategy: dict[str, Any]
    created_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    query: str
    sources: list[str]
    geo: dict[str, Any] | None = None
    research_config: dict[str, Any] | None = None
    status: str
    signal_count: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class RunDetailOut(RunOut):
    opportunities: list[OpportunityOut]
