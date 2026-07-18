from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    log: str = Field(min_length=1)
    service: Optional[str] = None
    environment: Optional[str] = None
    context: Optional[str] = None


class IncidentMatch(BaseModel):
    incident_id: str
    title: str
    date: str
    similarity: float
    summary: str
    tags: list[str]
    matched_keywords: list[str] = Field(default_factory=list)
    shared_concepts: list[str] = Field(default_factory=list)
    why_similar: str = ""


class AgentResult(BaseModel):
    agent: str
    status: str
    summary: str
    details: str
    confidence: float = Field(ge=0, le=1)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class DiagnosisResponse(BaseModel):
    status: Literal["complete"] = "complete"
    summary: str
    root_cause: str
    likely_matches: list[IncidentMatch]
    agents: list[AgentResult]
    prevention: list[str]
    skeptic_notes: list[str]
    stream_events: int
