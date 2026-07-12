# Omniscol Translation Pipeline — Version 2 (Semantic Localization Layer)

This extends the V1 AI Clinic pipeline (`scripts/01_fetch_from_api.py`,
`scripts/03_translation_pipeline.py`) with the semantic architecture
requested by the technical lead: concept-aware glossary, classification,
semantic batching, structural + semantic validation, and an LLM review
layer — instead of translating "200 random keys per chunk".

It runs against the **same data** V1 already produces (`data/source/*.json`,
`languages/*.json`) — nothing new needs to be fetched to try it.

## Why this exists

V1's own Polish audit (`languages/pl_webapp.audit.md`) already found a
concrete example of the problem: `action.activate` and `action.enable`
are distinct concepts in the product (activating an account vs. enabling
a setting) but both translate to **"Aktywuj"** in Polish. Nothing in V1's
pipeline could have caught that automatically — the validator only checks
placeholders/HTML/keys, and the audit relies on an LLM reading the whole
file and noticing it. V2's semantic layer catches this class of bug
**with a script, deterministically, with no API call**, alongside several
other real collisions in the current Polish file:

```
python scripts/04_semantic_pipeline.py audit-v2 --lang pl --module webapp
```
finds, among others:
- `action.activate` / `action.enable` → both "Aktywuj"
- `absence.reason.canceledclasses` (concept: class) / `sched.course.canceled`
  (concept: lesson) → both "Zajęcia odwołane"
- `diagnose.problem.spacesetdupl.descr` / `timesetdupl.descr` → identical
  rendered string, meaning the two diagnostic message templates are
  currently indistinguishable to a Polish user
- `subjects.import.from_class` / `groups.import.from_class` → both
  "Importuj z klasy"

These are exactly the kind of concept confusions the technical lead's
document describes as unacceptable (Class ≠ Lesson, Group ≠ Class, etc.).

## Architecture — mapped to the technical lead's document

| # | Stage (his spec) | Module | Status |
|---|---|---|---|
| 1 | Input normalization | `src/normalize.py` | **Done + tested** |
| 2 | Concept glossary | `config/concepts.json`, `src/glossary.py` | **Done** (17 concepts seeded from real data, extensible) |
| 3 | Canonical UI labels | `config/canonical_labels.json` | **Done** (seed set, needs expansion — see Limitations) |
| 4 | Key classification | `src/classify.py` | **Done + tested** |
| 5 | Semantic batching | `src/batch.py` | **Done** |
| 6 | Prompt builder | `src/prompt.py` | **Done** |
| 7 | Hard structural validation | `src/validate_structure.py` | **Done + tested** |
| 8 | Semantic consistency validation | `src/validate_semantics.py` | **Done + tested**, tuning needed (see Limitations) |
| 9 | LLM review pass | `src/review.py`, `src/llm_client.py` | **Interface done**, only tested against `MockLLMClient` |
| 10 | Human review queue | `src/export.py` (`render_review_queue_markdown`) | **Done** |
| 11 | Export | `src/export.py` (`export_results`) | **Done** |

Repository structure matches what he proposed:
```
config/        concepts.json, canonical_labels.json, forbidden_terms.json
src/           normalize, glossary, classify, batch, prompt, llm_client,
               validate_structure, validate_semantics, review, export
scripts/       04_semantic_pipeline.py (new CLI, sits alongside V1's 01/03)
tests/         19 passing unit tests, incl. a regression test for the
               real activate/enable bug
reports/v2/    audit + generation output lands here
```

## How to run it

Structural + semantic audit of an existing language file (no API needed):
```bash
python scripts/04_semantic_pipeline.py audit-v2 --lang pl --module webapp
```

Generate missing keys only, using the mock LLM (safe, no credentials needed):
```bash
python scripts/04_semantic_pipeline.py generate-v2 --lang pl --module webapp
```

Generate missing keys with real Gemini/Vertex (same credentials as V1 — needs
`config.py`'s `GCP_PROJECT_ID` and working `gcloud`/Vertex auth):
```bash
python scripts/04_semantic_pipeline.py generate-v2 --lang pl --module webapp --live
```

Run the test suite:
```bash
pip install pytest --break-system-packages
python -m pytest tests/ -v
```

## What's real vs. what's scoped as future work

I want to be precise about this so it's defensible if asked directly:

**Fully implemented and unit-tested today:**
- Normalization (placeholders, HTML tags, punctuation, capitalization, text type)
- Classification (module/action/entity tags from key path + French content)
- Semantic batching by dominant concept
- Structural validation (the V1 checks, plus HTML order/count, capitalization,
  punctuation, technical tokens)
- Semantic validation's core mechanism: Dice-coefficient concept matching +
  cross-concept collision detection — proven against real production data
  (finds 4 genuine bugs in the current Polish file, see above)
- Prompt construction, export, diff report, human review queue

**Implemented but only validated against a mock LLM, not a live one:**
- The translation call itself (`GeminiLLMClient` reuses V1's exact
  `google-genai`/Vertex AI setup, but I had no API credentials in this
  environment to run it live — the code path is the same one V1 already
  uses successfully in production, so risk here is low, but it hasn't been
  re-verified by me end-to-end this week)
- The LLM review pass (stage 9) — the prompt and plumbing exist, but its
  actual judgment quality is unverified without a live model

**Known limitation, not hidden:**
- The "expected concept term found in target" semantic check (stage 8)
  currently over-triggers on enumerated leaf values (e.g. individual
  `absence.reason.*` entries like "Sick leave" don't need to literally
  contain the word "absence") — it produces ~200 low-severity `REVIEW`
  flags on the real Polish webapp file that are mostly not real issues.
  It's scoped as REVIEW (lowest severity) rather than ERROR precisely
  because of this, but it needs a scope restriction (e.g. only check
  bare/near-bare concept keys, not every leaf under a namespace) before
  it's trustworthy enough to drive a human queue on its own. This is the
  single most valuable next fix.

**Not built this week, intentionally deferred:**
- Expanding `config/concepts.json` / `canonical_labels.json` beyond the
  seed set (17 concepts) to full glossary coverage across both modules
  (~1,289 keys)
- A real human-review UI (currently: a markdown file)
- CI/CD

## Next steps (priority order)
1. Fix the stage-8 over-triggering (scope concept-term checks to canonical/bare
   keys, not every leaf)
2. Run `generate-v2 --live` against one real target language end-to-end and
   compare LLM-review output quality against the mock
3. Expand the concept glossary using the full `Glossary.md` + a pass over
   all ~1,289 webapp keys (currently only the concepts appearing in
   `sched`, `absence`, `role`, `class`, `group`, `classroom`, `teacher` are seeded)
4. Wire `sync-missing-keys` (V1) to call into `generate-v2` instead of the
   flat chunker, once (1) and (2) are done
