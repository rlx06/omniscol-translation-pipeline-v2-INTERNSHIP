"""
Stage 1: Input normalization.

Turns a flat `key -> value` translation entry into the structured object
the technical lead's document specifies:

    { key, fr, en, target, namespace, placeholders, html_tags,
      trailing_punctuation, capitalization_pattern, text_type }

Omniscol has no separate English pivot file in the V1 data (the glossary
uses English only as the documentation language), so `en` is left None
unless one is explicitly supplied - the rest of the pipeline does not
depend on it being present.
"""
from __future__ import annotations

import re

from .models import NormalizedKey

PLACEHOLDER_PATTERNS = [
    r"\{\{[^{}]+\}\}",   # {{name}}
    r"\{[^{}]+\}",       # {name}
    r"%s",
    r"%d",
    r"%f",
]

HTML_TAG_PATTERN = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]*(?:\s[^<>]*)?>")

TRAILING_PUNCT = {"?", "!", ":", "...", "…"}

BUTTON_PREFIXES = ("action.",)
MESSAGE_PREFIXES = ("error.", "diagnose.")
TITLE_PREFIXES = ("html.title.",)


def extract_placeholders(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    found: list[str] = []
    remaining = text
    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, remaining)
        found.extend(matches)
    return sorted(set(found))


def extract_html_tags(text: str) -> list[str]:
    if not isinstance(text, str):
        return []
    return HTML_TAG_PATTERN.findall(text)


def extract_trailing_punctuation(text: str) -> str | None:
    if not isinstance(text, str) or not text.strip():
        return None
    stripped = text.rstrip()
    for punct in sorted(TRAILING_PUNCT, key=len, reverse=True):
        if stripped.endswith(punct):
            return punct
    if stripped and stripped[-1] in ".,;":
        return stripped[-1]
    return None


def detect_capitalization_pattern(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unknown"
    # Strip HTML/placeholders before inspecting case
    clean = HTML_TAG_PATTERN.sub("", text)
    for pattern in PLACEHOLDER_PATTERNS:
        clean = re.sub(pattern, "", clean)
    clean = clean.strip()
    if not clean:
        return "unknown"
    letters = [c for c in clean if c.isalpha()]
    if not letters:
        return "unknown"
    if clean.isupper():
        return "upper"
    if clean[0].isupper() and not any(c.isupper() for c in clean[1:]):
        return "sentence"
    words = clean.split()
    capitalized_words = [w for w in words if w[:1].isupper()]
    if len(words) > 1 and len(capitalized_words) / len(words) > 0.6:
        return "title"
    if clean[0].islower():
        return "lower"
    return "sentence"


def detect_text_type(key: str, text: str) -> str:
    if key.startswith(BUTTON_PREFIXES):
        return "button_or_label"
    if key.startswith(TITLE_PREFIXES):
        return "title"
    if key.startswith(MESSAGE_PREFIXES):
        return "message"
    if isinstance(text, str) and len(text) > 120:
        return "long_text"
    if isinstance(text, str) and extract_html_tags(text):
        return "rich_text"
    return "label"


def normalize_key(
    key: str,
    fr_value: str,
    target_value: str | None = None,
    en_value: str | None = None,
) -> NormalizedKey:
    namespace = key.split(".")[:-1] or [key]
    return NormalizedKey(
        key=key,
        fr=fr_value,
        en=en_value,
        target=target_value,
        namespace=namespace,
        placeholders=extract_placeholders(fr_value),
        html_tags=extract_html_tags(fr_value),
        trailing_punctuation=extract_trailing_punctuation(fr_value),
        capitalization_pattern=detect_capitalization_pattern(fr_value),
        text_type=detect_text_type(key, fr_value),
    )


def normalize_all(
    fr_translations: dict[str, str],
    target_translations: dict[str, str] | None = None,
) -> list[NormalizedKey]:
    target_translations = target_translations or {}
    return [
        normalize_key(key, fr_value, target_translations.get(key))
        for key, fr_value in fr_translations.items()
    ]
