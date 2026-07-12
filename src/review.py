"""
Stage 9: LLM review pass.

The LLM here is a reviewer of already-validated output, not the source
of truth - it runs after structural + semantic validation, and its output
is itself constrained to blockers/warnings/suggestions only.
"""
from __future__ import annotations

import json

from .llm_client import LLMClient
from .models import Batch


def build_review_prompt(batch: Batch, translations: dict[str, str], target_language: str) -> str:
    pairs = {
        nkey.key: {"fr": nkey.fr, "target": translations.get(nkey.key, nkey.target)}
        for nkey in batch.keys
    }
    return f"""You are reviewing already-validated {target_language} translations for the
Omniscol platform. You are NOT translating - only reviewing.

Check for:
- semantic drift (target meaning differs from French source)
- wrong concept choice (e.g. confusing two distinct concepts)
- informal tone where formal register is required
- missed reuse of canonical UI labels
- excessive stylistic rewriting
- suspicious/likely-wrong translations in long texts

Entries to review:
{json.dumps(pairs, ensure_ascii=False, indent=2)}

Return JSON only, in this exact shape:
{{
  "blockers": ["key: reason", ...],
  "warnings": ["key: reason", ...],
  "suggestions": ["key: reason", ...]
}}
"""


def run_llm_review(
    batch: Batch,
    translations: dict[str, str],
    target_language: str,
    client: LLMClient,
) -> dict:
    prompt = build_review_prompt(batch, translations, target_language)
    return client.review(prompt)
