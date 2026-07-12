"""
Stage 7: Hard structural validation. No LLM involved.

Extends V1's validate_translation_chunk (JSON validity, missing/extra keys,
placeholder preservation, French-leak detection) with the additional
structural checks the technical lead's document calls "absolute rules":
HTML tag count/order, capitalization pattern, trailing punctuation, and
untouched technical tokens (&nbsp; etc).
"""
from __future__ import annotations

from .models import NormalizedKey, ValidationIssue
from .normalize import (
    extract_html_tags,
    extract_placeholders,
    extract_trailing_punctuation,
    detect_capitalization_pattern,
)

TECHNICAL_TOKENS = ["&nbsp;", "&amp;", "&lt;", "&gt;", "&quot;"]


def validate_structure(nkey: NormalizedKey, translated_text: str | None) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    key = nkey.key

    if translated_text is None:
        issues.append(ValidationIssue(key, "BLOCKER", "Missing key in target translation", "structural"))
        return issues

    if not isinstance(translated_text, str):
        issues.append(ValidationIssue(key, "BLOCKER", "Translated value is not a string", "structural"))
        return issues

    if not translated_text.strip():
        issues.append(ValidationIssue(key, "BLOCKER", "Translated value is empty", "structural"))
        return issues

    # Placeholders
    source_placeholders = set(nkey.placeholders)
    target_placeholders = set(extract_placeholders(translated_text))
    if source_placeholders != target_placeholders:
        issues.append(ValidationIssue(
            key, "BLOCKER",
            f"Placeholder mismatch: source={sorted(source_placeholders)} target={sorted(target_placeholders)}",
            "structural",
        ))

    # HTML tags: same count and same order
    source_tags = nkey.html_tags
    target_tags = extract_html_tags(translated_text)
    if source_tags != target_tags:
        issues.append(ValidationIssue(
            key, "BLOCKER",
            f"HTML tag mismatch: source={source_tags} target={target_tags}",
            "structural",
        ))

    # Technical tokens must survive untouched
    for token in TECHNICAL_TOKENS:
        if token in nkey.fr and token not in translated_text:
            issues.append(ValidationIssue(
                key, "ERROR", f"Technical token '{token}' present in source but missing in target", "structural",
            ))

    # Trailing punctuation
    source_punct = nkey.trailing_punctuation
    target_punct = extract_trailing_punctuation(translated_text)
    if source_punct != target_punct:
        issues.append(ValidationIssue(
            key, "WARNING",
            f"Trailing punctuation differs: source={source_punct!r} target={target_punct!r}",
            "structural",
        ))

    # Capitalization pattern (only for short label-like text - long text naturally varies)
    if nkey.text_type in ("button_or_label", "title", "label"):
        target_pattern = detect_capitalization_pattern(translated_text)
        if nkey.capitalization_pattern not in ("unknown",) and target_pattern != nkey.capitalization_pattern:
            issues.append(ValidationIssue(
                key, "WARNING",
                f"Capitalization pattern differs: source={nkey.capitalization_pattern} target={target_pattern}",
                "structural",
            ))

    return issues


def validate_all_structure(
    nkeys: list[NormalizedKey],
    target_translations: dict[str, str],
) -> list[ValidationIssue]:
    all_issues: list[ValidationIssue] = []
    for nkey in nkeys:
        all_issues.extend(validate_structure(nkey, target_translations.get(nkey.key)))
    return all_issues
