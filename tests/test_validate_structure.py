import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.normalize import normalize_key
from src.validate_structure import validate_structure


def _severities(issues):
    return {i.severity for i in issues}


def test_catches_placeholder_mismatch():
    nkey = normalize_key("k", "Bonjour {name}")
    issues = validate_structure(nkey, "Hello there")  # dropped {name}
    assert "BLOCKER" in _severities(issues)


def test_catches_html_tag_mismatch():
    nkey = normalize_key("k", "<b>Merci</b>")
    issues = validate_structure(nkey, "Merci")  # dropped tags
    assert "BLOCKER" in _severities(issues)


def test_catches_missing_key():
    nkey = normalize_key("k", "Bonjour")
    issues = validate_structure(nkey, None)
    assert issues[0].severity == "BLOCKER"


def test_catches_empty_translation():
    nkey = normalize_key("k", "Bonjour")
    issues = validate_structure(nkey, "   ")
    assert any(i.severity == "BLOCKER" for i in issues)


def test_valid_translation_has_no_blockers():
    nkey = normalize_key("action.confirm", "Confirmer")
    issues = validate_structure(nkey, "Potwierdz")
    assert not any(i.severity == "BLOCKER" for i in issues)


def test_placeholders_preserved_passes():
    nkey = normalize_key("sched.course.info", "{time} de {subject}")
    issues = validate_structure(nkey, "{time} z {subject}")
    assert not any(i.severity == "BLOCKER" for i in issues)
