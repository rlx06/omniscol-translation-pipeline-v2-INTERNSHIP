"""
Stage 6: Prompt builder. Produces the strict, closed prompt described in
the technical lead's document: translate only missing keys, preserve
placeholders/HTML/punctuation/capitalization exactly, use formal register,
reuse glossary terms, JSON-only output, flag uncertainty instead of guessing.
"""
from __future__ import annotations

import json

from .glossary import ConceptGlossary
from .models import Batch


def build_prompt(
    batch: Batch,
    glossary: ConceptGlossary,
    canonical_labels: dict,
    target_language: str,
) -> str:
    glossary_subset = glossary.subset(batch.concepts_involved)

    relevant_labels = {
        k: v for k, v in canonical_labels.items()
        if v.get("concept_id") in batch.concepts_involved
    }

    forbidden_terms = sorted({
        confusion
        for cid in batch.concepts_involved
        for confusion in glossary.forbidden_confusions(cid)
    })

    source_payload = {nkey.key: nkey.fr for nkey in batch.keys if nkey.target is None}

    return f"""You are a professional localization translator working on the Omniscol
school-scheduling platform. Translate French UI strings into {target_language}.

STRICT RULES (all mandatory):
- Translate only the keys given below. Do not invent, skip, or rename keys.
- Preserve every placeholder exactly, e.g. {{name}}, %s, %d, and any HTML tags such as <b> or <br>.
- Preserve the final punctuation of each source string (?, !, :, ...).
- Preserve the capitalization pattern (sentence case, title case, etc).
- Use formal register only.
- Reuse the canonical UI labels below wherever the same concept appears in a longer string -
  do not invent alternate wording for a concept that already has an official label.
- The following concepts must NEVER be translated using each other's wording, even though
  the French source may reuse the same word for both: {forbidden_terms or "(none for this batch)"}
- Do not rewrite stylistically. Translate as literally as is natural in {target_language}.
- If you are not confident about a translation, return it in "flags" with a short reason
  instead of guessing.
- Return JSON only, no explanation, no markdown fences.

Canonical UI labels for this batch (source of truth for naming these concepts):
{json.dumps(relevant_labels, ensure_ascii=False, indent=2)}

Concept glossary for this batch (meaning + forbidden confusions):
{json.dumps(glossary_subset, ensure_ascii=False, indent=2)}

Keys to translate (batch: {batch.name}, {len(source_payload)} keys):
{json.dumps(source_payload, ensure_ascii=False, indent=2)}

Output format (JSON only):
{{
  "translations": {{ "key.name": "translated value" }},
  "flags": {{ "key.name": "reason for uncertainty" }}
}}
"""
