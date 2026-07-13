# Omniscol Translation Pipeline — Version 2

A semantic, concept-aware localization pipeline for the Omniscol school-scheduling
platform, built during an internship as a continuation of the AI Clinic project.

## What this solves

Omniscol's UI text exists in ~1,289 keys per language (login + webapp modules),
across 14 languages. The original pipeline (V1) translated these by splitting
each file into arbitrary blocks of 200 keys and sending each block to Gemini
with a generic prompt. This scaled, but had no concept of *meaning*: two
distinct product concepts that happen to share a French word (e.g. "activate"
an account vs. "enable" a setting - both `Activer` in French) could be
translated identically, with nothing catching it.

V2 replaces that with a pipeline that understands the product's own
vocabulary — batching by concept, validating structure *and* meaning, and
remembering every translation decision so it's never made inconsistently
twice.

## Architecture

```
   French source ──> Normalize ──> Classify ──> Semantic Batch
                                                      |
                                                      v
                                            Translation Memory
                                          (reuse if seen before)
                                                      |
                                            not seen? v
                                                  Translate (Gemini)
                                                      |
                                                      v
                                        +-- Structural Validation
                                        |-- Semantic Validation
                                        |-- Canonical Validation
                                        +-- LLM Review
                                                      |
                                                      v
                                                   Export
                              (final JSON, diff, review queue, summary)
```

Run `python scripts/04_semantic_pipeline.py demo --lang <code> --module <webapp|login>`
to see every one of these stages execute, in order, with real output at
each step — the fastest way to understand what the pipeline actually does.

## Pipeline stages

| # | Stage | Module | What it does |
|---|---|---|---|
| 1 | Normalize | `src/normalize.py` | Extracts placeholders, HTML tags, punctuation, capitalization pattern from each key |
| 2 | Classify | `src/classify.py` | Tags each key with its module, action, and matched concept(s) |
| 3 | Semantic batch | `src/batch.py` | Groups keys by shared concept instead of arbitrary position |
| 4 | Translation memory | `src/translation_memory.py` | Reuses the existing translation for identical French text instead of re-asking the LLM |
| 5 | Translate | `src/prompt.py`, `src/llm_client.py` | Builds a closed, glossary-aware prompt per batch and calls Gemini (or a mock client for safe local testing) |
| 6 | Structural validation | `src/validate_structure.py` | Placeholders, HTML tag structure, punctuation, capitalization, technical tokens |
| 7 | Semantic validation | `src/validate_semantics.py` | Concept-confusion detection + same-source-text consistency |
| 8 | Canonical validation | `src/validate_canonical.py` | Flags when a canonical UI label's translation has drifted from its baseline |
| 9 | LLM review | `src/review.py` | A second LLM pass reviewing (not generating) translations for tone/drift |
| 10 | Export | `src/export.py` | Writes the final JSON, a diff report, a human review queue, and a manager-facing summary scorecard |

## Folder structure

```
omniscol_v2/
├── config/                    concept glossary, canonical labels, forbidden-term pairs
├── data/source/                French reference JSON (fr_webapp.json, fr_login.json)
├── languages/                  one JSON per language, {lang}_{module}.json
├── memory/                     translation_memory.json (grows automatically, gitignored data)
├── reports/v2/                 audit/generate/sync output: diffs, review queues, summaries
├── scripts/
│   ├── 01_fetch_from_api.py     V1: pulls latest French reference from the API
│   ├── 03_translation_pipeline.py  V1: original 200-key chunker (kept, unchanged)
│   └── 04_semantic_pipeline.py     V2: audit-v2 / generate-v2 / sync-v2 / demo
├── src/                        the V2 pipeline modules (see table above)
└── tests/                      35 unit tests covering every module
```

## How to run it

```bash
pip install -r requirements.txt --break-system-packages

# See the whole pipeline run end-to-end, stage by stage, in one command:
python scripts/04_semantic_pipeline.py demo --lang pl --module webapp

# Validate an existing language file - no API calls, fully deterministic:
python scripts/04_semantic_pipeline.py audit-v2 --lang pl --module webapp

# Translate missing keys for one language (mock by default, safe):
python scripts/04_semantic_pipeline.py generate-v2 --lang pl --module webapp
python scripts/04_semantic_pipeline.py generate-v2 --lang pl --module webapp --live

# Sync missing keys across every language at once (replaces V1's 200-key chunker):
python scripts/04_semantic_pipeline.py sync-v2            # preview only, safe
python scripts/04_semantic_pipeline.py sync-v2 --live      # writes to real files, auto-backs-up first

python -m pytest tests/ -v
```

## Example output

Running `audit-v2` against real production Polish data surfaces a scorecard
first, then a detailed, severity-sorted list:

```
# Pipeline Summary — webapp (pl)

- Total keys: 1223
- Missing keys: 0
- Semantic (concept-confusion) errors: 8
- Canonical label violations: 1

## Overall score: 97%
```

followed by specifics, e.g.:

```
[ERROR] action.activate (semantic): Forbidden concept confusion:
'action.activate' and 'action.enable' both translate to 'Aktywuj' -
these concepts must not collapse together.
```

## Continuous integration

`.github/workflows/python.yml` runs the full test suite automatically on
every push and pull request via GitHub Actions.

## Recent additions (in response to external code review)

- **Translation memory** — identical French text is never translated two
  different ways across separate keys or separate runs.
- **Canonical label enforcement** — flags drift in a canonical UI label's
  translation from its established baseline.
- **Same-source consistency check** — flags existing drift where identical
  French text already has inconsistent translations.
- **Pipeline summary scorecard** — a one-glance health report per language,
  generated automatically by `audit-v2` and `generate-v2`.
- **`demo` command** — the full pipeline, stage by stage, in one command.

## V1 pipeline (still present, unchanged)

`scripts/01_fetch_from_api.py` and `scripts/03_translation_pipeline.py`
still work independently: fetch the French reference from the Omniscol API,
translate via 200-key chunks, validate structurally, and sync missing keys.
V2 does not replace these files - it adds `scripts/04_semantic_pipeline.py`
alongside them, and `sync-v2` is the semantic-pipeline equivalent of V1's
`sync_missing_keys()`.

## What's real vs. what's scoped as future work

**Fully implemented and unit-tested (35 tests):** normalization,
classification, semantic batching, translation memory, structural
validation, semantic validation, canonical validation, export, and the
end-to-end `demo` command.

**Verified against live Gemini, not only a mock client:** translation
generation for missing keys (40 keys synced live across 6 languages during
development, spot-checked for fluency and correctness).

**Known limitations, disclosed rather than hidden:**
- The concept glossary and canonical label set currently cover 17 seed
  concepts (schedule, absence, role, class, group, classroom, teacher),
  not the full ~1,289-key vocabulary. Both grow automatically as more
  languages are processed, but full coverage is not yet complete.
- The semantic "expected concept term" check over-triggers on enumerated
  leaf values (e.g. individual absence-reason entries don't need to
  literally contain the word "absence") - flagged at the lowest severity
  (`REVIEW`) for this reason, but needs scope-tightening.
- The LLM review pass's judgment quality on already-translated content has
  not yet been validated against a large real sample.

## Future work

- Expand the concept glossary and canonical labels to full coverage across
  all product namespaces (admin, diagnose, error, staffing, wishes, course).
- Investigate whether the `timesetdupl`/`spacesetdupl` template collision
  (identical in all 14 languages, see `reports/v2/cross_language_findings.md`)
  originates in the French source itself.
- Wire V1's `sync_missing_keys()` to call `sync-v2` directly, fully
  retiring the 200-key chunker from the active code path.
- Expose `generate-v2` as an internal API so an entirely new language (e.g.
  onboarding a school in a new region) can be generated from zero through
  the same pipeline used for routine maintenance, with the human review
  queue as a gate before going live.
