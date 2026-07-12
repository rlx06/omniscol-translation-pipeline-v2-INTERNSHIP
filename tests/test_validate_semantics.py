import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.classify import classify_all
from src.glossary import ConceptGlossary
from src.load import load_concepts, load_forbidden_pairs
from src.normalize import normalize_all
from src.validate_semantics import dice_coefficient, validate_semantics

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _glossary():
    return ConceptGlossary(load_concepts(CONFIG_DIR))


def test_dice_coefficient_identical_strings():
    assert dice_coefficient("klasa", "klasa") == 1.0


def test_dice_coefficient_unrelated_strings_low():
    assert dice_coefficient("klasa", "xyzabc") < 0.2


def test_regression_activate_enable_collision_is_caught():
    """This is the exact real-world bug found in languages/pl_webapp.audit.md:
    action.activate and action.enable both translate to 'Aktywuj' in Polish,
    even though they are distinct concepts (forbidden_confusions in concepts.json)."""
    glossary = _glossary()
    forbidden_pairs = load_forbidden_pairs(CONFIG_DIR)

    fr = {"action.activate": "Activer", "action.enable": "Activer"}
    pl = {"action.activate": "Aktywuj", "action.enable": "Aktywuj"}

    nkeys = normalize_all(fr, pl)
    classify_all(nkeys, glossary)

    issues = validate_semantics(nkeys, pl, glossary, "pl", forbidden_pairs)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert errors, "Expected the activate/enable collision to be flagged as ERROR"
    assert any("activate" in i.message and "enable" in i.message for i in errors)


def test_no_false_positive_when_translations_differ():
    glossary = _glossary()
    forbidden_pairs = load_forbidden_pairs(CONFIG_DIR)

    fr = {"action.activate": "Activer", "action.enable": "Activer"}
    pl = {"action.activate": "Aktywuj", "action.enable": "Wlacz"}  # correctly distinct

    nkeys = normalize_all(fr, pl)
    classify_all(nkeys, glossary)

    issues = validate_semantics(nkeys, pl, glossary, "pl", forbidden_pairs)
    errors = [i for i in issues if i.severity == "ERROR"]
    assert not errors


def test_same_source_consistency_catches_drift():
    from src.validate_semantics import validate_same_source_consistency

    fr = {"button.cancel.a": "Annuler", "button.cancel.b": "Annuler"}
    pl_inconsistent = {"button.cancel.a": "Anuluj", "button.cancel.b": "Przerwij"}

    nkeys = normalize_all(fr, pl_inconsistent)
    issues = validate_same_source_consistency(nkeys, pl_inconsistent)
    assert len(issues) == 1
    assert issues[0].severity == "WARNING"


def test_same_source_consistency_no_false_positive_when_consistent():
    from src.validate_semantics import validate_same_source_consistency

    fr = {"button.cancel.a": "Annuler", "button.cancel.b": "Annuler"}
    pl_consistent = {"button.cancel.a": "Anuluj", "button.cancel.b": "Anuluj"}

    nkeys = normalize_all(fr, pl_consistent)
    issues = validate_same_source_consistency(nkeys, pl_consistent)
    assert issues == []
