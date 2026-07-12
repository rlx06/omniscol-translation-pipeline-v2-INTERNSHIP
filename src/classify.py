"""
Stage 4: Classification.

Each key gets multiple tags, using three signals as specified:
  - key path (e.g. sched.course.assign_teachers)
  - French/English content (matched against the concept glossary)
  - namespace membership (keys sharing the same prefix)

A key can land in several consistency groups at once, e.g.
["entity.teacher", "constraint.conflict", "message.warning"].
"""
from __future__ import annotations

from .glossary import ConceptGlossary
from .models import NormalizedKey

ACTION_VERBS = {
    "assign", "create", "edit", "delete", "add", "cancel", "confirm",
    "close", "view", "import", "export", "download", "print", "generate",
    "reset", "activate", "enable", "deactivate", "declare", "validate",
    "duplicate", "reorganize", "remove", "search",
}


def _module_tag(namespace: list[str]) -> str:
    return f"module.{namespace[0]}" if namespace else "module.unknown"


def _action_tag(key: str) -> str | None:
    last_segment = key.split(".")[-1]
    for verb in ACTION_VERBS:
        if verb in last_segment:
            return f"action.{verb}"
    return None


def _message_tag(text_type: str) -> str:
    return f"message.{text_type}"


def classify_key(nkey: NormalizedKey, glossary: ConceptGlossary) -> list[str]:
    tags = [_module_tag(nkey.namespace)]

    action_tag = _action_tag(nkey.key)
    if action_tag:
        tags.append(action_tag)

    tags.append(_message_tag(nkey.text_type))

    # Concept/entity matches: key path words are English-like, French content is French
    key_readable = nkey.key.replace(".", " ").replace("_", " ")
    matched = set(glossary.concepts_matching_text(key_readable, lang="en"))
    matched |= set(glossary.concepts_matching_text(nkey.fr, lang="fr"))
    for concept_id in sorted(matched):
        tags.append(f"entity.{concept_id}")

    return sorted(set(tags))


def classify_all(nkeys: list[NormalizedKey], glossary: ConceptGlossary) -> None:
    """Mutates each NormalizedKey in place, filling `.tags`."""
    for nkey in nkeys:
        nkey.tags = classify_key(nkey, glossary)
