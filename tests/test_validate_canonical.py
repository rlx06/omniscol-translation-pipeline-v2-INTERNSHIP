import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.validate_canonical import validate_canonical_labels


def test_no_drift_when_translation_matches_stored_canonical():
    canonical_labels = {
        "sched.hours_distribution.title": {
            "concept_id": "hours_distribution",
            "fr": "Repartition des heures",
            "pl": "Rozklad godzin",
        }
    }
    target_translations = {"sched.hours_distribution.title": "Rozklad godzin"}
    issues = validate_canonical_labels(target_translations, canonical_labels, "pl")
    assert issues == []


def test_flags_drift_when_translation_differs_from_stored_canonical():
    canonical_labels = {
        "sched.hours_distribution.title": {
            "concept_id": "hours_distribution",
            "fr": "Repartition des heures",
            "pl": "Rozklad godzin",
        }
    }
    target_translations = {"sched.hours_distribution.title": "Podzial godzin"}
    issues = validate_canonical_labels(target_translations, canonical_labels, "pl")
    assert len(issues) == 1
    assert issues[0].severity == "ERROR"
    assert "drift" in issues[0].message.lower()


def test_no_issue_when_no_stored_baseline_yet():
    canonical_labels = {
        "sched.hours_distribution.title": {"concept_id": "hours_distribution", "fr": "..."}
    }
    target_translations = {"sched.hours_distribution.title": "Anything"}
    issues = validate_canonical_labels(target_translations, canonical_labels, "pl")
    assert issues == []


def test_no_issue_when_key_missing_from_target():
    canonical_labels = {
        "sched.hours_distribution.title": {
            "concept_id": "hours_distribution",
            "fr": "Repartition des heures",
            "pl": "Rozklad godzin",
        }
    }
    issues = validate_canonical_labels({}, canonical_labels, "pl")
    assert issues == []
