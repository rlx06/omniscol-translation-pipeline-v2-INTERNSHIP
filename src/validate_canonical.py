"""
Canonical label enforcement.

config/canonical_labels.json defines the single source-of-truth
translation for each concept's official UI label. Injecting it into the
prompt (src/prompt.py) is necessary but not sufficient - nothing
previously checked that the actual translated output still matches it.
This module closes that gap: it detects when a canonical label's own key
has drifted from the stored canonical translation (e.g. "Hours
Distribution" becoming "Distribution of Hours" in a later regeneration).

First-time setup: if config/canonical_labels.json has no stored target
for a given language yet, there is nothing to drift from - use
bootstrap_canonical_targets() once to capture the current translation as
the new baseline. After that, any change is flagged.
"""
from __future__ import annotations

from pathlib import Path

from .load import load_json, save_json
from .models import ValidationIssue

RESERVED_FIELDS = {"concept_id", "fr", "en", "is_canonical_label"}


def validate_canonical_labels(
    target_translations: dict[str, str],
    canonical_labels: dict,
    lang: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for key, entry in canonical_labels.items():
        if key == "_comment":
            continue
        stored = entry.get(lang)
        current = target_translations.get(key)
        if stored is None or current is None:
            continue
        # Case-insensitive comparison: many canonical sources (e.g. a
        # dictionary/glossary file) store terms in lowercase, while real UI
        # text is capitalized per normal sentence/title case. That's a
        # capitalization convention, not a drift in the actual word choice -
        # capitalization pattern is already checked separately in structural
        # validation. Only flag a genuine wording change here.
        if stored.strip().lower() != current.strip().lower():
            issues.append(ValidationIssue(
                key, "ERROR",
                f"Canonical label drift: stored canonical translation for concept "
                f"'{entry.get('concept_id')}' is {stored!r}, but current file has "
                f"{current!r}. Canonical labels must not change once set - if this "
                f"change is intentional, update config/canonical_labels.json deliberately.",
                "canonical",
            ))
    return issues


def bootstrap_canonical_targets(
    config_dir: Path, target_translations: dict[str, str], lang: str,
) -> int:
    """Capture the current translation of each canonical label key as the
    new baseline for `lang`, where none exists yet. Returns count added."""
    path = Path(config_dir) / "canonical_labels.json"
    labels = load_json(path)
    added = 0
    for key, entry in labels.items():
        if key == "_comment":
            continue
        current = target_translations.get(key)
        if current is None:
            continue
        if lang not in entry:
            entry[lang] = current
            added += 1
    if added:
        save_json(labels, path)
    return added
