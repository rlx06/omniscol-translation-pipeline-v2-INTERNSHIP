"""
Stage 5: Semantic batching.

Replaces "200 arbitrary keys per chunk" with batches grouped by the
dominant entity/concept tag, so every batch shares glossary context
instead of mixing unrelated domains.
"""
from __future__ import annotations

from collections import defaultdict

from .models import Batch, NormalizedKey

FALLBACK_BATCH = "misc"


def _primary_concept(nkey: NormalizedKey) -> str:
    entity_tags = [t for t in nkey.tags if t.startswith("entity.")]
    if entity_tags:
        # Deterministic: pick alphabetically first for stability across runs
        return sorted(entity_tags)[0].replace("entity.", "")
    module_tags = [t for t in nkey.tags if t.startswith("module.")]
    if module_tags:
        return module_tags[0].replace("module.", "")
    return FALLBACK_BATCH


def build_batches(nkeys: list[NormalizedKey], max_batch_size: int = 60) -> list[Batch]:
    grouped: dict[str, list[NormalizedKey]] = defaultdict(list)
    for nkey in nkeys:
        grouped[_primary_concept(nkey)].append(nkey)

    batches: list[Batch] = []
    for name, keys in grouped.items():
        # Split oversized semantic groups (e.g. "sched") into numbered sub-batches
        # rather than letting a single batch exceed a workable prompt size.
        for i in range(0, len(keys), max_batch_size):
            chunk = keys[i:i + max_batch_size]
            suffix = f"_{i // max_batch_size + 1}" if len(keys) > max_batch_size else ""
            concepts_involved = {
                t.replace("entity.", "")
                for k in chunk for t in k.tags if t.startswith("entity.")
            }
            batches.append(Batch(name=f"{name}{suffix}", keys=chunk, concepts_involved=concepts_involved))

    return sorted(batches, key=lambda b: b.name)
