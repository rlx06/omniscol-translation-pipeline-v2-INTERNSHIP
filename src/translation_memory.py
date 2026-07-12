"""
Translation memory.

Addresses the exact problem flagged in review: without this, the same
French source text can be translated inconsistently across separate runs
or separate keys - e.g. "Professeur" -> "Nauczyciel" today, then
"Professeurs" -> "Wychowawca" (wrong) three weeks later, with nothing
catching the drift.

Design: keyed by (target_language, normalized French text) -> the
translation already committed for that exact text. Before asking the LLM
to translate a missing key, the pipeline checks memory first. Only text
genuinely new to a language is sent to Gemini; everything else is reused
deterministically.

This is deliberately keyed by normalized TEXT, not by key name, because
the goal is "same source sentence must always produce the same
translation" regardless of which key it lives under - two keys can
legitimately share the exact same French label (e.g. two different
buttons both saying "Annuler") and must still get the same translation.
"""
from __future__ import annotations

from pathlib import Path

from .glossary import _norm
from .load import load_json, save_json


class TranslationMemory:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists():
            self._data: dict[str, dict[str, dict]] = load_json(self.path)
        else:
            self._data = {}

    def lookup(self, lang: str, fr_text: str) -> str | None:
        entry = self._data.get(lang, {}).get(_norm(fr_text))
        return entry["translation"] if entry else None

    def record(self, lang: str, fr_text: str, translation: str, source_key: str) -> None:
        self._data.setdefault(lang, {})[_norm(fr_text)] = {
            "translation": translation,
            "fr_text": fr_text,
            "first_seen_key": source_key,
        }

    def bootstrap_from_existing(
        self, lang: str, fr_translations: dict[str, str], target_translations: dict[str, str],
    ) -> int:
        """Populate memory from an already-translated, presumed-correct file.
        Returns how many new entries were added. Existing memory entries are
        never overwritten by this - bootstrap only fills gaps."""
        added = 0
        lang_mem = self._data.setdefault(lang, {})
        for key, fr_text in fr_translations.items():
            target_text = target_translations.get(key)
            if not target_text:
                continue
            norm_key = _norm(fr_text)
            if norm_key not in lang_mem:
                lang_mem[norm_key] = {
                    "translation": target_text,
                    "fr_text": fr_text,
                    "first_seen_key": key,
                }
                added += 1
        return added

    def save(self) -> None:
        save_json(self._data, self.path)

    def stats(self) -> dict[str, int]:
        return {lang: len(entries) for lang, entries in self._data.items()}
