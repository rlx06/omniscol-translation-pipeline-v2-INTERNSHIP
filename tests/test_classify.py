import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.classify import classify_key
from src.glossary import ConceptGlossary
from src.load import load_concepts
from src.normalize import normalize_key

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _glossary():
    return ConceptGlossary(load_concepts(CONFIG_DIR))


def test_classify_teacher_assignment_key():
    glossary = _glossary()
    nkey = normalize_key("sched.course.assign_teachers", "Affecter des professeurs")
    tags = classify_key(nkey, glossary)
    assert "module.sched" in tags
    assert "entity.teacher" in tags


def test_classify_action_verb_detected():
    glossary = _glossary()
    nkey = normalize_key("action.activate", "Activer")
    tags = classify_key(nkey, glossary)
    assert any(t.startswith("action.") for t in tags)
    assert "entity.activate" in tags


def test_classify_conflict_key():
    glossary = _glossary()
    nkey = normalize_key("diagnose.conflict.title", "Conflit detecte")
    tags = classify_key(nkey, glossary)
    assert "entity.conflict" in tags
