"""
Stage 2: The concept glossary.

Not a word list (fr_word -> target_word). Each entry is a concept with
surface forms per language, a meaning, and the other concepts it must
never be confused with - matching the technical lead's spec.
"""
from __future__ import annotations

import unicodedata


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _norm(text: str) -> str:
    return _strip_accents(text).lower()


class ConceptGlossary:
    def __init__(self, concepts: dict):
        self.concepts = concepts
        # Pre-normalize forms for matching
        self._forms_by_concept: dict[str, dict[str, list[str]]] = {}
        for concept_id, entry in concepts.items():
            forms = {}
            for field_name, value in entry.items():
                if field_name.endswith("_forms") and isinstance(value, list):
                    lang = field_name.replace("_forms", "")
                    forms[lang] = [_norm(f) for f in value]
            self._forms_by_concept[concept_id] = forms

    def concept_ids(self) -> list[str]:
        return list(self.concepts.keys())

    def concepts_matching_text(self, text: str, lang: str = "fr") -> list[str]:
        """Return every concept whose surface form for `lang` appears in `text`."""
        if not isinstance(text, str) or not text.strip():
            return []
        norm_text = _norm(text)
        matches = []
        for concept_id, forms in self._forms_by_concept.items():
            for form in forms.get(lang, []):
                if form and form in norm_text:
                    matches.append(concept_id)
                    break
        return matches

    def forbidden_confusions(self, concept_id: str) -> list[str]:
        return self.concepts.get(concept_id, {}).get("forbidden_confusions", [])

    def target_forms(self, concept_id: str, lang: str) -> list[str]:
        return self._forms_by_concept.get(concept_id, {}).get(lang, [])

    def meaning(self, concept_id: str) -> str:
        return self.concepts.get(concept_id, {}).get("meaning", "")

    def subset(self, concept_ids: set[str]) -> dict:
        """A minimal glossary slice for prompt injection - only relevant concepts."""
        return {cid: self.concepts[cid] for cid in concept_ids if cid in self.concepts}
