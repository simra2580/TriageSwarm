from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import IncidentMatch


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    title: str
    date: str
    service: str | None
    summary: str
    details: str
    tags: list[str]


class IncidentStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else Path(__file__).with_name("incidents.json")
        self._records = self._load()

    def _load(self) -> list[IncidentRecord]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [IncidentRecord(**item) for item in raw]

    def all(self) -> list[IncidentRecord]:
        return list(self._records)

    def search(self, log_text: str, service: str | None = None, keywords: Iterable[str] = (), limit: int = 3) -> list[IncidentMatch]:
        query_tokens = _tokenize(log_text)
        if service:
            query_tokens.append(service.lower())
        for keyword in keywords:
            query_tokens.extend(_tokenize(keyword))

        query_set = set(query_tokens)
        scored: list[tuple[float, IncidentRecord, list[str], list[str]]] = []
        for record in self._records:
            score, matched_keywords, shared_concepts = _score_record(record, query_set, service)
            scored.append((score, record, matched_keywords, shared_concepts))

        scored.sort(key=lambda item: (item[0], item[1].date), reverse=True)
        return [
            IncidentMatch(
                incident_id=record.id,
                title=record.title,
                date=record.date,
                similarity=round(score, 3),
                summary=record.summary,
                tags=record.tags,
                matched_keywords=matched_keywords,
                shared_concepts=shared_concepts,
                why_similar=_why_similar(matched_keywords, shared_concepts, record),
            )
            for score, record, matched_keywords, shared_concepts in scored[:limit]
            if score > 0
        ]

    def summarize_match_patterns(self, matches: Iterable[IncidentMatch]) -> list[str]:
        patterns: list[str] = []
        for match in matches:
            patterns.append(f"{match.incident_id}: {match.summary}")
        return patterns


_STOPWORDS = {
    "the",
    "and",
    "or",
    "to",
    "of",
    "a",
    "in",
    "for",
    "with",
    "on",
    "at",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "this",
    "that",
    "it",
    "an",
    "as",
    "after",
    "before",
    "into",
    "when",
    "while",
    "during",
    "through",
    "into",
    "over",
    "under",
}

_SUBSYSTEM_HINTS = {
    "auth": {"auth", "login", "token", "session", "credential", "refresh"},
    "gateway": {"gateway", "edge", "router", "proxy", "limiter", "rate limit"},
    "retry": {"retry", "backoff", "storm", "replay", "amplify"},
    "webhooks": {"webhook", "delivery", "fanout", "duplicate"},
    "checkout": {"checkout", "payments", "cart", "payment"},
    "queue": {"queue", "worker", "consumer", "lag", "depth"},
}

_ERROR_HINTS = {
    "timeout": {"timeout", "timed out", "deadline", "504"},
    "auth failure": {"401", "403", "unauthorized", "forbidden", "invalid token", "expired token"},
    "rate limit": {"429", "rate limit", "throttle", "limited"},
    "retry storm": {"retry", "backoff", "storm", "loop"},
    "stale credential": {"stale", "credential", "refresh token", "expired", "rotation"},
    "duplicate delivery": {"duplicate", "replay", "fanout", "double"},
}


def _tokenize(text: str) -> list[str]:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in text)
    return [token for token in normalized.split() if token and token not in _STOPWORDS]


def _score_record(record: IncidentRecord, tokens: set[str], service: str | None) -> tuple[float, list[str], list[str]]:
    record_tokens = set(_tokenize(" ".join([record.title, record.summary, record.details, " ".join(record.tags)])))
    overlap = tokens & record_tokens
    matched_keywords = sorted(overlap)

    shared_concepts = []
    for tag in record.tags:
        tag_tokens = set(_tokenize(tag))
        if tokens & tag_tokens:
            shared_concepts.append(tag)

    concept_score = len(overlap) * 1.1
    tag_score = len(shared_concepts) * 0.8
    service_bonus = 0.0
    if service and record.service and service.lower() == record.service.lower():
        service_bonus = 2.0

    title_bonus = 0.0
    title_tokens = set(_tokenize(record.title))
    if tokens & title_tokens:
        title_bonus = 1.0

    error_bonus = 0.0
    joined = " ".join([record.title, record.summary, record.details]).lower()
    for label, hints in _ERROR_HINTS.items():
        if any(hint in joined for hint in hints) and any(hint in " ".join(tokens) for hint in hints):
            error_bonus = max(error_bonus, 1.0)
            if label not in shared_concepts:
                shared_concepts.append(label)

    subsystem_bonus = 0.0
    for label, hints in _SUBSYSTEM_HINTS.items():
        if any(hint in " ".join(tokens) for hint in hints) and any(hint in joined for hint in hints):
            subsystem_bonus = max(subsystem_bonus, 0.9)
            if label not in shared_concepts:
                shared_concepts.append(label)

    score = concept_score + tag_score + service_bonus + title_bonus + error_bonus + subsystem_bonus
    return score, matched_keywords[:8], sorted(set(shared_concepts))


def _why_similar(matched_keywords: list[str], shared_concepts: list[str], record: IncidentRecord) -> str:
    pieces: list[str] = []
    if matched_keywords:
        pieces.append(f"shared keywords: {', '.join(matched_keywords[:4])}")
    if shared_concepts:
        pieces.append(f"shared concepts: {', '.join(shared_concepts[:4])}")
    if record.service:
        pieces.append(f"same service focus: {record.service}")
    return "; ".join(pieces) if pieces else "broad narrative similarity"
