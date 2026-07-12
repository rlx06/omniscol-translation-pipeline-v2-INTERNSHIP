import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.normalize import (
    extract_placeholders, extract_html_tags, extract_trailing_punctuation,
    detect_capitalization_pattern, detect_text_type, normalize_key,
)


def test_extract_placeholders():
    assert extract_placeholders("{time} de {subject}") == ["{subject}", "{time}"]
    assert extract_placeholders("Hello %s, you have %d messages") == ["%d", "%s"]
    assert extract_placeholders("no placeholders here") == []


def test_extract_html_tags_preserves_order_and_count():
    text = "<b>Merci</b><br><br>Suite"
    assert extract_html_tags(text) == ["<b>", "</b>", "<br>", "<br>"]


def test_trailing_punctuation():
    assert extract_trailing_punctuation("Choisissez une série") is None
    assert extract_trailing_punctuation("Etes-vous sûr ?") == "?"
    assert extract_trailing_punctuation("Attention !") == "!"


def test_capitalization_pattern():
    assert detect_capitalization_pattern("EXPORT") == "upper"
    assert detect_capitalization_pattern("Nom de la classe") == "sentence"
    assert detect_capitalization_pattern("Hours Distribution") == "title"


def test_text_type_from_key_prefix():
    assert detect_text_type("action.activate", "Activer") == "button_or_label"
    assert detect_text_type("html.title.login", "Accueil") == "title"
    assert detect_text_type("error.something", "Bad") == "message"


def test_normalize_key_builds_namespace():
    nkey = normalize_key("sched.course.assign_teachers", "Affecter des professeurs")
    assert nkey.namespace == ["sched", "course"]
    assert nkey.fr == "Affecter des professeurs"
    assert nkey.target is None
