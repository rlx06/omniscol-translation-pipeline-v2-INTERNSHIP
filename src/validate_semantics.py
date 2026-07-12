"""
Stage 8: Semantic consistency validation. No exact-word matching, because
grammar/declension changes surface forms across languages - matching uses
Dice coefficient bigram overlap, not str equality.

This is also where the concrete bug flagged in the audit
(action.activate / action.enable both -> "Aktywuj" in Polish) gets caught
programmatically: two keys tagged with mutually-forbidden concepts whose
target strings collapse to the same text is a structural signal that the
concept distinction has been lost in translation.
"""
from __future__ import annotations

from collections import defaultdict

from .glossary import ConceptGlossary, _norm
from .models import NormalizedKey, ValidationIssue


def _bigrams(text: str) -> set[str]:
    text = _norm(text)
    return {text[i:i + 2] for i in range(len(text) - 1)} or {text}


def dice_coefficient(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    bigrams_a, bigrams_b = _bigrams(a), _bigrams(b)
    overlap = len(bigrams_a & bigrams_b)
    return (2.0 * overlap) / (len(bigrams_a) + len(bigrams_b))


def validate_semantics(
    nkeys: list[NormalizedKey],
    target_translations: dict[str, str],
    glossary: ConceptGlossary,
    target_lang: str,
    forbidden_pairs: list[tuple[str, str]],
    similarity_threshold: float = 0.35,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # index: concept_id -> list of (key, target_text)
    by_concept: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for nkey in nkeys:
        target_text = target_translations.get(nkey.key)
        if not target_text:
            continue

        expected_concepts = [t.replace("entity.", "") for t in nkey.tags if t.startswith("entity.")]
        for concept_id in expected_concepts:
            by_concept[concept_id].append((nkey.key, target_text))

        if not expected_concepts:
            continue

        # Does the target contain an allowed form for at least one expected concept?
        matched_any = False
        for concept_id in expected_concepts:
            forms = glossary.target_forms(concept_id, target_lang)
            if not forms:
                continue
            for form in forms:
                if dice_coefficient(form, target_text) >= similarity_threshold or form in _norm(target_text):
                    matched_any = True
                    break
            if matched_any:
                break

        has_known_forms = any(glossary.target_forms(c, target_lang) for c in expected_concepts)
        if has_known_forms and not matched_any:
            issues.append(ValidationIssue(
                nkey.key, "REVIEW",
                f"Expected concept term for {expected_concepts} not clearly found in target text {target_text!r}",
                "semantic",
            ))

    # Cross-concept collision: forbidden pairs whose target strings collapse together
    for concept_a, concept_b in forbidden_pairs:
        entries_a = by_concept.get(concept_a, [])
        entries_b = by_concept.get(concept_b, [])
        for key_a, text_a in entries_a:
            for key_b, text_b in entries_b:
                if key_a == key_b:
                    continue
                if _norm(text_a) == _norm(text_b):
                    issues.append(ValidationIssue(
                        key_a, "ERROR",
                        f"Forbidden concept confusion: '{key_a}' (concept={concept_a}) and "
                        f"'{key_b}' (concept={concept_b}) both translate to {text_a!r} - "
                        f"these concepts must not collapse together (see config/concepts.json).",
                        "semantic",
                    ))

    return issues
