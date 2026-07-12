"""
Data model for the semantic translation pipeline (V2).

This module has no external dependencies and no side effects - it only
defines the shapes that flow between pipeline stages, matching the object
described in the technical lead's architecture document (step 1,
"Input normalization").
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NormalizedKey:
    key: str
    fr: str
    en: str | None
    target: str | None
    namespace: list[str]
    placeholders: list[str]
    html_tags: list[str]
    trailing_punctuation: str | None
    capitalization_pattern: str
    text_type: str
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "fr": self.fr,
            "en": self.en,
            "target": self.target,
            "namespace": self.namespace,
            "placeholders": self.placeholders,
            "html_tags": self.html_tags,
            "trailing_punctuation": self.trailing_punctuation,
            "capitalization_pattern": self.capitalization_pattern,
            "text_type": self.text_type,
            "tags": self.tags,
        }


@dataclass
class Batch:
    name: str
    keys: list[NormalizedKey]
    concepts_involved: set[str]

    def __len__(self) -> int:
        return len(self.keys)


@dataclass
class ValidationIssue:
    key: str
    severity: str  # BLOCKER | ERROR | WARNING | REVIEW
    message: str
    stage: str  # structural | semantic | llm_review

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "severity": self.severity,
            "message": self.message,
            "stage": self.stage,
        }


SEVERITY_ORDER = {"BLOCKER": 0, "ERROR": 1, "WARNING": 2, "REVIEW": 3}
