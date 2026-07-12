import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.translation_memory import TranslationMemory


def _temp_memory():
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    return TranslationMemory(tmp)


def test_lookup_returns_none_when_empty():
    mem = _temp_memory()
    assert mem.lookup("pl", "Professeur") is None


def test_record_then_lookup():
    mem = _temp_memory()
    mem.record("pl", "Professeur", "Nauczyciel", "role.teacher")
    assert mem.lookup("pl", "Professeur") == "Nauczyciel"


def test_lookup_is_case_and_accent_insensitive():
    mem = _temp_memory()
    mem.record("pl", "professeur", "Nauczyciel", "role.teacher")
    assert mem.lookup("pl", "PROFESSEUR") == "Nauczyciel"


def test_memory_isolated_per_language():
    mem = _temp_memory()
    mem.record("pl", "Professeur", "Nauczyciel", "role.teacher")
    assert mem.lookup("de", "Professeur") is None


def test_bootstrap_from_existing_fills_gaps_without_overwriting():
    mem = _temp_memory()
    mem.record("pl", "Professeur", "Nauczyciel-manual", "role.teacher")

    fr = {"role.teacher": "Professeur", "role.student": "Eleve"}
    target = {"role.teacher": "Nauczyciel-old", "role.student": "Uczen"}
    added = mem.bootstrap_from_existing("pl", fr, target)

    assert added == 1  # only role.student was new
    assert mem.lookup("pl", "Professeur") == "Nauczyciel-manual"  # not overwritten
    assert mem.lookup("pl", "Eleve") == "Uczen"


def test_save_and_reload_round_trip():
    tmp = Path(tempfile.mkdtemp()) / "memory.json"
    mem = TranslationMemory(tmp)
    mem.record("pl", "Professeur", "Nauczyciel", "role.teacher")
    mem.save()

    reloaded = TranslationMemory(tmp)
    assert reloaded.lookup("pl", "Professeur") == "Nauczyciel"
