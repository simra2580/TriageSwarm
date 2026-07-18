from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .incident_store import IncidentStore, _tokenize
from .models import AgentResult, DiagnoseRequest, IncidentMatch


@dataclass(frozen=True)
class LogAnalysis:
    affected_service: str
    probable_subsystem: str
    error_type: str
    severity: str
    keywords: list[str]
    probable_root_cause: str
    summary: str
    confidence_reasoning: str
    confidence: float
    completeness: float
    certainty: float
    source: str


@dataclass(frozen=True)
class HypothesisDraft:
    summary: str
    root_cause: str
    evidence: list[str]
    confidence: float


@dataclass(frozen=True)
class SkepticReview:
    summary: str
    objections: list[str]
    confidence: float
    alternative: str | None = None


@dataclass(frozen=True)
class PreventionPlan:
    summary: str
    actions: list[str]
    confidence: float


_SERVICE_HINTS = {
    "checkout": {"checkout", "payment", "payments", "cart", "order"},
    "webhooks": {"webhook", "fanout", "delivery", "duplicate"},
    "auth": {"auth", "login", "token", "session", "credential", "refresh"},
    "api-gateway": {"gateway", "edge", "proxy", "limiter", "429"},
    "worker": {"worker", "job", "queue", "consumer", "lag"},
}

_SUBSYSTEM_HINTS = {
    "credential refresh": {"refresh", "token", "credential", "rotation"},
    "retry control": {"retry", "backoff", "storm", "loop"},
    "traffic shaping": {"rate limit", "429", "throttle", "limiter"},
    "delivery fanout": {"fanout", "duplicate", "delivery", "webhook"},
    "queue processing": {"queue", "worker", "lag", "depth"},
}

_ERROR_HINTS = {
    "timeout": {"timeout", "timed out", "504", "deadline"},
    "authentication failure": {"401", "403", "unauthorized", "forbidden", "invalid token", "expired token"},
    "rate limit exhaustion": {"429", "rate limit", "throttle", "limited"},
    "retry amplification": {"retry", "backoff", "storm", "loop"},
    "stale credential refresh": {"stale", "refresh token", "credential", "rotation"},
    "duplicate delivery": {"duplicate", "replay", "fanout", "double"},
}

_JSON_SCHEMA: dict[str, Any] = {
    "name": "incident_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "affected_service": {"type": "string"},
            "subsystem": {"type": "string"},
            "error_type": {"type": "string"},
            "severity": {"type": "string"},
            "important_keywords": {
                "type": "array",
                "items": {"type": "string"},
            },
            "probable_root_cause": {"type": "string"},
            "summary": {"type": "string"},
            "confidence_reasoning": {"type": "string"},
        },
        "required": [
            "affected_service",
            "subsystem",
            "error_type",
            "severity",
            "important_keywords",
            "probable_root_cause",
            "summary",
            "confidence_reasoning",
        ],
    },
}


class LogAnalyzerAgent:
    name = "Log Analyzer"

    def __init__(self, model: str | None = None, timeout_seconds: float = 8.0) -> None:
        self.model = model or os.getenv("TRIAGESWARM_OPENAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
        self.timeout_seconds = timeout_seconds

    def run(self, request: DiagnoseRequest) -> LogAnalysis:
        log = request.log.strip()
        completeness = _log_completeness(log)
        payload = self._call_openai(request, log)
        if payload is not None:
            try:
                return _analysis_from_payload(payload, request, completeness, source="openai")
            except ValueError:
                pass
        return _deterministic_analysis(request, completeness)

    def _call_openai(self, request: DiagnoseRequest, log: str) -> dict[str, Any] | None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "You analyze incident logs. Return only valid JSON that matches the schema exactly. "
                    "Do not add markdown, code fences, or extra keys."
                ),
            },
            {
                "role": "user",
                "content": _build_user_prompt(request, log),
            },
        ]

        body = json.dumps(
            {
                "model": self.model,
                "temperature": 0,
                "messages": messages,
                "response_format": {"type": "json_schema", "json_schema": _JSON_SCHEMA},
            }
        ).encode("utf-8")

        request_obj = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request_obj, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
            return None

        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None

        if not isinstance(content, str):
            return None

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


class HistorianAgent:
    name = "Historian"

    def __init__(self, store: IncidentStore) -> None:
        self.store = store

    def run(self, request: DiagnoseRequest, analysis: LogAnalysis) -> list[IncidentMatch]:
        service = analysis.affected_service if analysis.affected_service != "unknown service" else request.service
        return self.store.search(request.log, service=service, keywords=analysis.keywords, limit=3)


class HypothesisAgent:
    name = "Hypothesis"

    def run(self, analysis: LogAnalysis, matches: list[IncidentMatch]) -> HypothesisDraft:
        if matches:
            primary = matches[0]
            similarity_signal = f"{primary.similarity:.2f} similarity to {primary.incident_id}"
            root_cause = _combine_root_cause(analysis.probable_root_cause, primary.summary)
            evidence = [
                f"Current log suggests {analysis.error_type} in {analysis.probable_subsystem}",
                f"Closest historical match: {primary.incident_id} ({primary.title})",
                f"Why similar: {primary.why_similar}",
            ]
            summary = f"The failure most likely shares the same shape as {primary.title.lower()}, with {similarity_signal}."
            confidence = _clamp(
                0.34
                + (analysis.certainty * 0.24)
                + (analysis.completeness * 0.14)
                + (primary.similarity * 0.24)
                + (0.08 if len(matches) > 1 else 0.0)
            )
        else:
            root_cause = analysis.probable_root_cause
            evidence = [
                f"Current log suggests {analysis.error_type} in {analysis.probable_subsystem}",
                "No historical incident crossed the similarity threshold.",
            ]
            summary = "New incident pattern detected."
            confidence = _clamp(0.24 + (analysis.certainty * 0.28) + (analysis.completeness * 0.18))
        return HypothesisDraft(summary=summary, root_cause=root_cause, evidence=evidence, confidence=confidence)


class SkepticAgent:
    name = "Skeptic"

    def run(self, request: DiagnoseRequest, analysis: LogAnalysis, hypothesis: HypothesisDraft, matches: list[IncidentMatch]) -> SkepticReview:
        objections = [
            f"The log is strongest on {analysis.error_type}, but it may hide the upstream trigger.",
            f"The diagnosis leans on {analysis.probable_subsystem}, which could still be a downstream symptom.",
        ]
        alternative = None

        if matches:
            top = matches[0]
            objections.append(f"Historical similarity is helpful, but {top.incident_id} only matches at {top.similarity:.2f}.")
            confidence = _clamp(hypothesis.confidence + (analysis.certainty * 0.05) + (top.similarity * 0.04))
        else:
            alternative = f"Alternative explanation: the issue may sit in {analysis.affected_service} instrumentation or an unlogged dependency spike."
            objections.append("No historical twin was found, so the diagnosis should stay provisional.")
            confidence = _clamp(hypothesis.confidence - (0.06 - analysis.certainty * 0.02))

        if request.environment:
            objections.append(f"Environment hint: {request.environment} may change the failure shape.")

        summary = "The diagnosis is plausible, but it still needs a tighter upstream causal chain."
        return SkepticReview(summary=summary, objections=objections, confidence=confidence, alternative=alternative)


class PreventionArchitectAgent:
    name = "Prevention Architect"

    def run(self, analysis: LogAnalysis, hypothesis: HypothesisDraft, skeptic: SkepticReview, matches: list[IncidentMatch]) -> PreventionPlan:
        actions = _prevention_actions(analysis, hypothesis, matches, skeptic.alternative)
        summary = f"Prevent recurrence by addressing {analysis.error_type.lower()} in {analysis.probable_subsystem}."
        confidence = _clamp(
            0.3
            + (analysis.certainty * 0.2)
            + (analysis.completeness * 0.14)
            + (hypothesis.confidence * 0.2)
            + (0.06 if matches else -0.02)
        )
        return PreventionPlan(summary=summary, actions=actions, confidence=confidence)


def to_agent_result(name: str, status: str, summary: str, details: str, confidence: float, **artifacts: Any) -> AgentResult:
    return AgentResult(agent=name, status=status, summary=summary, details=details, confidence=confidence, artifacts=artifacts)


def _build_user_prompt(request: DiagnoseRequest, log: str) -> str:
    context_bits = [
        "Analyze the complete incident log below.",
        "Return only JSON that matches the schema.",
        f"service hint: {request.service or 'unknown'}",
        f"environment hint: {request.environment or 'unknown'}",
        f"context hint: {request.context or 'none'}",
        "log:",
        log,
    ]
    return "\n".join(context_bits)


def _analysis_from_payload(payload: dict[str, Any], request: DiagnoseRequest, completeness: float, source: str) -> LogAnalysis:
    affected_service = _require_text(payload.get("affected_service")) or _infer_service(request.log, request.service)
    probable_subsystem = _require_text(payload.get("subsystem"))
    error_type = _require_text(payload.get("error_type"))
    severity = _require_text(payload.get("severity"))
    keywords = _normalize_keywords(payload.get("important_keywords"))
    probable_root_cause = _require_text(payload.get("probable_root_cause"))
    summary = _require_text(payload.get("summary"))
    confidence_reasoning = _require_text(payload.get("confidence_reasoning"))

    if not all([affected_service, probable_subsystem, error_type, severity, probable_root_cause, summary, confidence_reasoning]) or not keywords:
        raise ValueError("incomplete openai payload")

    certainty = _field_certainty(
        affected_service,
        probable_subsystem,
        error_type,
        severity,
        keywords,
        probable_root_cause,
        summary,
        confidence_reasoning,
        completeness,
    )
    confidence = _clamp(0.2 + (certainty * 0.3) + (completeness * 0.18))
    return LogAnalysis(
        affected_service=affected_service,
        probable_subsystem=probable_subsystem,
        error_type=error_type,
        severity=severity,
        keywords=keywords,
        probable_root_cause=probable_root_cause,
        summary=summary,
        confidence_reasoning=confidence_reasoning,
        confidence=confidence,
        completeness=completeness,
        certainty=certainty,
        source=source,
    )


def _deterministic_analysis(request: DiagnoseRequest, completeness: float) -> LogAnalysis:
    log = request.log.strip()
    lowered = log.lower()
    tokens = _tokenize(log)

    affected_service = request.service or _best_label(lowered, _SERVICE_HINTS, "unknown service")
    probable_subsystem = _best_label(lowered, _SUBSYSTEM_HINTS, "application core")
    error_type = _best_label(lowered, _ERROR_HINTS, "general service failure")
    severity = _severity_from_log(log, completeness)
    keywords = _extract_keywords(log)
    probable_root_cause = _infer_root_cause(error_type, probable_subsystem, affected_service)
    summary = _build_summary(affected_service, probable_subsystem, error_type, severity)
    confidence_reasoning = _deterministic_reasoning(affected_service, probable_subsystem, error_type, severity, keywords, completeness)
    certainty = _field_certainty(
        affected_service,
        probable_subsystem,
        error_type,
        severity,
        keywords,
        probable_root_cause,
        summary,
        confidence_reasoning,
        completeness,
    )
    confidence = _clamp(0.18 + (certainty * 0.28) + (completeness * 0.2) + (len(tokens) * 0.002))
    return LogAnalysis(
        affected_service=affected_service,
        probable_subsystem=probable_subsystem,
        error_type=error_type,
        severity=severity,
        keywords=keywords,
        probable_root_cause=probable_root_cause,
        summary=summary,
        confidence_reasoning=confidence_reasoning,
        confidence=confidence,
        completeness=completeness,
        certainty=certainty,
        source="deterministic",
    )


def _best_label(text: str, hints: dict[str, set[str]], fallback: str) -> str:
    lowered = text.lower()
    best = fallback
    best_score = 0
    for label, candidates in hints.items():
        score = sum(1 for candidate in candidates if candidate in lowered)
        if score > best_score:
            best = label
            best_score = score
    return best


def _extract_keywords(log: str) -> list[str]:
    tokens = _tokenize(log)
    seen: list[str] = []
    for token in tokens:
        if token not in seen and len(token) > 2:
            seen.append(token)
    return seen[:12]


def _build_summary(service: str, subsystem: str, error_type: str, severity: str) -> str:
    return f"{severity.capitalize()} {error_type} affecting {service} around {subsystem}."


def _log_completeness(log: str) -> float:
    tokens = _tokenize(log)
    if not tokens:
        return 0.1
    return min(1.0, max(0.1, len(tokens) / 40))


def _severity_from_log(log: str, completeness: float) -> str:
    lowered = log.lower()
    if any(token in lowered for token in ["critical", "outage", "down", "abort", "500", "503", "504", "failed"]):
        return "critical"
    if any(token in lowered for token in ["timeout", "error rate", "spike", "429", "unauthorized", "forbidden"]):
        return "high"
    if completeness < 0.35:
        return "medium"
    return "medium"


def _infer_service(log: str, fallback: str | None) -> str:
    return fallback or _best_label(log.lower(), _SERVICE_HINTS, "unknown service")


def _infer_root_cause(error_type: str, subsystem: str, service: str) -> str:
    if error_type == "authentication failure":
        return f"{service} is rejecting valid traffic because {subsystem} cannot establish a stable credential state"
    if error_type == "timeout":
        return f"{service} is timing out while waiting on {subsystem}"
    if error_type == "rate limit exhaustion":
        return f"Shared capacity in {subsystem} is being exhausted faster than it recovers"
    if error_type == "retry amplification":
        return f"Retries in {subsystem} are amplifying an existing failure instead of recovering from it"
    if error_type == "duplicate delivery":
        return f"{subsystem} is replaying work and producing duplicate side effects"
    if error_type == "stale credential refresh":
        return f"{service} is failing because {subsystem} is not refreshing credentials cleanly"
    return f"{service} is experiencing an unresolved failure in {subsystem}"


def _combine_root_cause(current: str, historical_summary: str) -> str:
    historical = historical_summary.rstrip(".")
    if current.lower() in historical.lower():
        return historical_summary
    return f"{current}; similar incidents describe {historical.lower()}"


def _prevention_actions(analysis: LogAnalysis, hypothesis: HypothesisDraft, matches: list[IncidentMatch], alternative: str | None) -> list[str]:
    actions = [
        f"Add an alert when {analysis.error_type.lower()} appears in {analysis.affected_service}.",
        f"Reduce blast radius in {analysis.probable_subsystem} with bounded retries and clear failure budgets.",
        f"Add a runbook check for {analysis.probable_root_cause.lower()} before reprocessing requests.",
    ]

    if analysis.error_type == "authentication failure" or "credential" in analysis.probable_root_cause.lower():
        actions.append("Rotate or refresh credentials earlier and watch for token drift before the next deploy.")
    elif analysis.error_type == "rate limit exhaustion":
        actions.append("Throttle the noisiest caller first and isolate the shared limiter from unrelated traffic.")
    elif analysis.error_type == "duplicate delivery":
        actions.append("Deduplicate deliveries at the boundary and make retries idempotent.")
    elif analysis.error_type == "timeout":
        actions.append("Trace upstream latency and stop retrying once the downstream service is already saturated.")
    elif analysis.error_type == "retry amplification":
        actions.append("Break the retry loop at the first saturated hop instead of retrying the whole chain.")

    if matches:
        actions.append(f"Capture this pattern next to {matches[0].incident_id} so the next responder sees the historical context immediately.")
    elif alternative:
        actions.append("Instrument the suspected upstream boundary so the next incident can be classified faster.")

    return actions[:5]


def _analysis_summary_score(value: str) -> float:
    tokens = _tokenize(value)
    if not tokens:
        return 0.0
    distinct = len(set(tokens))
    return min(1.0, 0.1 + distinct * 0.08)


def _field_certainty(
    affected_service: str,
    subsystem: str,
    error_type: str,
    severity: str,
    keywords: list[str],
    probable_root_cause: str,
    summary: str,
    confidence_reasoning: str,
    completeness: float,
) -> float:
    filled = sum(
        1
        for value in [
            affected_service,
            subsystem,
            error_type,
            severity,
            probable_root_cause,
            summary,
            confidence_reasoning,
        ]
        if value.strip()
    )
    keyword_factor = min(0.2, len(keywords) * 0.025)
    text_factor = min(
        0.2,
        _analysis_summary_score(probable_root_cause)
        + _analysis_summary_score(summary)
        + _analysis_summary_score(confidence_reasoning),
    )
    return _clamp(0.18 + (filled * 0.07) + keyword_factor + text_factor + (completeness * 0.14))


def _deterministic_reasoning(
    affected_service: str,
    subsystem: str,
    error_type: str,
    severity: str,
    keywords: list[str],
    completeness: float,
) -> str:
    keyword_text = ", ".join(keywords[:5]) if keywords else "no strong keywords"
    return (
        f"Detected {severity} {error_type} in {affected_service} centered on {subsystem}; "
        f"signal coverage is {completeness:.2f} with keywords {keyword_text}."
    )


def _normalize_keywords(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    keywords: list[str] = []
    for item in raw:
        if isinstance(item, str):
            value = item.strip()
            if value and value not in keywords:
                keywords.append(value)
    return keywords[:12]


def _require_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 3)
