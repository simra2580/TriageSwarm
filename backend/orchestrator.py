from __future__ import annotations

import json
from typing import Any, AsyncIterator

from agents import (
    HistorianAgent,
    HypothesisAgent,
    LogAnalyzerAgent,
    PreventionArchitectAgent,
    SkepticAgent,
    to_agent_result,
)
from incident_store import IncidentStore
from models import DiagnoseRequest, DiagnosisResponse


class DiagnosisOrchestrator:
    def __init__(self, store: IncidentStore | None = None) -> None:
        self.store = store or IncidentStore()
        self.log_analyzer = LogAnalyzerAgent()
        self.historian = HistorianAgent(self.store)
        self.hypothesis = HypothesisAgent()
        self.skeptic = SkepticAgent()
        self.prevention = PreventionArchitectAgent()

    async def stream(self, request: DiagnoseRequest) -> AsyncIterator[dict[str, Any]]:
        yield self._event("session_started", {"message": "Diagnosis started"})

        yield self._event("agent_started", {"agent": self.log_analyzer.name})
        analysis = self.log_analyzer.run(request)
        yield self._event(
            "agent_result",
            {
                "agent": self.log_analyzer.name,
                "summary": analysis.summary,
                "details": "Affected service: "
                + analysis.affected_service
                + " | subsystem: "
                + analysis.probable_subsystem
                + " | error type: "
                + analysis.error_type
                + " | severity: "
                + analysis.severity,
                "confidence": analysis.confidence,
                "data": analysis.__dict__,
            },
        )

        yield self._event("agent_started", {"agent": self.historian.name})
        matches = self.historian.run(request, analysis)
        historian_summary = "Found " + str(len(matches)) + " historical match(es)" if matches else "New incident pattern detected."
        historian_details = (
            "Matches were selected dynamically from incidents.json using keyword and similarity scoring."
            if matches
            else "No incident cleared the similarity threshold."
        )
        yield self._event(
            "agent_result",
            {
                "agent": self.historian.name,
                "summary": historian_summary,
                "details": historian_details,
                "confidence": _historian_confidence(matches, analysis),
                "data": [match.model_dump() for match in matches],
            },
        )

        yield self._event("agent_started", {"agent": self.hypothesis.name})
        hypothesis = self.hypothesis.run(analysis, matches)
        yield self._event(
            "agent_result",
            {
                "agent": self.hypothesis.name,
                "summary": hypothesis.summary,
                "details": "Evidence: " + "; ".join(hypothesis.evidence),
                "confidence": hypothesis.confidence,
                "data": hypothesis.__dict__,
            },
        )

        yield self._event("agent_started", {"agent": self.skeptic.name})
        skepticism = self.skeptic.run(request, analysis, hypothesis, matches)
        skeptic_details = "Objections: " + " | ".join(skepticism.objections)
        if skepticism.alternative:
            skeptic_details += " | Alternative: " + skepticism.alternative
        yield self._event(
            "agent_result",
            {
                "agent": self.skeptic.name,
                "summary": skepticism.summary,
                "details": skeptic_details,
                "confidence": skepticism.confidence,
                "data": skepticism.__dict__,
            },
        )

        yield self._event("agent_started", {"agent": self.prevention.name})
        prevention = self.prevention.run(analysis, hypothesis, skepticism, matches)
        yield self._event(
            "agent_result",
            {
                "agent": self.prevention.name,
                "summary": prevention.summary,
                "details": "Actions: " + " | ".join(prevention.actions),
                "confidence": prevention.confidence,
                "data": prevention.__dict__,
            },
        )

        agent_results = [
            to_agent_result(
                self.log_analyzer.name,
                "complete",
                analysis.summary,
                "Affected service: "
                + analysis.affected_service
                + " | subsystem: "
                + analysis.probable_subsystem
                + " | error type: "
                + analysis.error_type
                + " | severity: "
                + analysis.severity
                + " | source: "
                + analysis.source,
                analysis.confidence,
                affected_service=analysis.affected_service,
                probable_subsystem=analysis.probable_subsystem,
                error_type=analysis.error_type,
                severity=analysis.severity,
                keywords=analysis.keywords,
                probable_root_cause=analysis.probable_root_cause,
                confidence_reasoning=analysis.confidence_reasoning,
                completeness=analysis.completeness,
                certainty=analysis.certainty,
                source=analysis.source,
            ),
            to_agent_result(
                self.historian.name,
                "complete",
                historian_summary,
                historian_details,
                _historian_confidence(matches, analysis),
                matches=[match.model_dump() for match in matches],
            ),
            to_agent_result(
                self.hypothesis.name,
                "complete",
                hypothesis.summary,
                "; ".join(hypothesis.evidence),
                hypothesis.confidence,
                root_cause=hypothesis.root_cause,
                evidence=hypothesis.evidence,
            ),
            to_agent_result(
                self.skeptic.name,
                "complete",
                skepticism.summary,
                skeptic_details,
                skepticism.confidence,
                objections=skepticism.objections,
                alternative=skepticism.alternative,
            ),
            to_agent_result(
                self.prevention.name,
                "complete",
                prevention.summary,
                " | ".join(prevention.actions),
                prevention.confidence,
                actions=prevention.actions,
            ),
        ]

        response = DiagnosisResponse(
            summary=prevention.summary,
            root_cause=hypothesis.root_cause,
            likely_matches=matches,
            agents=agent_results,
            prevention=prevention.actions,
            skeptic_notes=skepticism.objections,
            stream_events=12,
        )
        yield self._event("complete", response.model_dump())

    def diagnose(self, request: DiagnoseRequest) -> DiagnosisResponse:
        analysis = self.log_analyzer.run(request)
        matches = self.historian.run(request, analysis)
        hypothesis = self.hypothesis.run(analysis, matches)
        skepticism = self.skeptic.run(request, analysis, hypothesis, matches)
        prevention = self.prevention.run(analysis, hypothesis, skepticism, matches)
        historian_summary = "Found " + str(len(matches)) + " historical match(es)" if matches else "New incident pattern detected."
        historian_details = (
            "Matches were selected dynamically from incidents.json using keyword and similarity scoring."
            if matches
            else "No incident cleared the similarity threshold."
        )
        skeptic_details = "Objections: " + " | ".join(skepticism.objections)
        if skepticism.alternative:
            skeptic_details += " | Alternative: " + skepticism.alternative
        return DiagnosisResponse(
            summary=prevention.summary,
            root_cause=hypothesis.root_cause,
            likely_matches=matches,
            agents=[
                to_agent_result(
                    self.log_analyzer.name,
                    "complete",
                    analysis.summary,
                    "Affected service: "
                    + analysis.affected_service
                    + " | subsystem: "
                    + analysis.probable_subsystem
                    + " | error type: "
                    + analysis.error_type
                    + " | severity: "
                    + analysis.severity
                    + " | source: "
                    + analysis.source,
                    analysis.confidence,
                    affected_service=analysis.affected_service,
                    probable_subsystem=analysis.probable_subsystem,
                    error_type=analysis.error_type,
                    severity=analysis.severity,
                    keywords=analysis.keywords,
                    probable_root_cause=analysis.probable_root_cause,
                    confidence_reasoning=analysis.confidence_reasoning,
                    completeness=analysis.completeness,
                    certainty=analysis.certainty,
                    source=analysis.source,
                ),
                to_agent_result(
                    self.historian.name,
                    "complete",
                    historian_summary,
                    historian_details,
                    _historian_confidence(matches, analysis),
                    matches=[match.model_dump() for match in matches],
                ),
                to_agent_result(
                    self.hypothesis.name,
                    "complete",
                    hypothesis.summary,
                    "; ".join(hypothesis.evidence),
                    hypothesis.confidence,
                    root_cause=hypothesis.root_cause,
                    evidence=hypothesis.evidence,
                ),
                to_agent_result(
                    self.skeptic.name,
                    "complete",
                    skepticism.summary,
                    skeptic_details,
                    skepticism.confidence,
                    objections=skepticism.objections,
                    alternative=skepticism.alternative,
                ),
                to_agent_result(
                    self.prevention.name,
                    "complete",
                    prevention.summary,
                    " | ".join(prevention.actions),
                    prevention.confidence,
                    actions=prevention.actions,
                ),
            ],
            prevention=prevention.actions,
            skeptic_notes=skepticism.objections,
            stream_events=12,
        )

    @staticmethod
    def _event(event: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"event": event, "data": data}


def _historian_confidence(matches: list[Any], analysis: Any) -> float:
    if not matches:
        return _clamp(0.18 + (analysis.certainty * 0.14) + (analysis.completeness * 0.08))
    top = matches[0].similarity if matches else 0.0
    spread = matches[-1].similarity if len(matches) > 1 else top
    return _clamp(0.26 + (top * 0.28) + (analysis.certainty * 0.12) + (spread * 0.05))


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)


def format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
