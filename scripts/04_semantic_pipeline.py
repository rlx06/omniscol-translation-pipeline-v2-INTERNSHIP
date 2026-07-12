"""
Orchestrator for the semantic translation pipeline (V2).

Commands:
  audit-v2      Run structural + semantic validation against an EXISTING
                target language file (no LLM, no API calls) - this is the
                fastest way to see the pipeline catch real bugs, like the
                action.activate / action.enable collision already flagged
                in languages/pl_webapp.audit.md.

  generate-v2   Full pipeline for missing keys only: normalize -> classify
                -> batch -> prompt -> translate -> validate structural ->
                validate semantic -> LLM review -> export.
                Uses --mock by default (no API access required); pass
                --live to use GeminiLLMClient with the same config.py
                credentials as V1's scripts/03_translation_pipeline.py.

Run from the repo root, e.g.:
  python scripts/04_semantic_pipeline.py audit-v2 --lang pl --module webapp
  python scripts/04_semantic_pipeline.py generate-v2 --lang pl --module webapp --mock
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import FR_LOGIN_FILE, FR_WEBAPP_FILE, GCP_LOCATION, GCP_PROJECT_ID, GEMINI_MODEL, LANGUAGES_DIR

from src.batch import build_batches
from src.classify import classify_all
from src.export import export_results
from src.glossary import ConceptGlossary
from src.llm_client import GeminiLLMClient, MockLLMClient
from src.load import load_canonical_labels, load_concepts, load_forbidden_pairs, load_translations, save_json
from src.models import ValidationIssue
from src.normalize import normalize_all
from src.prompt import build_prompt
from src.review import run_llm_review
from src.validate_semantics import validate_semantics, validate_same_source_consistency
from src.validate_canonical import validate_canonical_labels, bootstrap_canonical_targets
from src.translation_memory import TranslationMemory

MEMORY_PATH = Path(__file__).resolve().parent.parent / "memory" / "translation_memory.json"
from src.validate_structure import validate_all_structure

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
REPORTS_V2_DIR = Path(__file__).resolve().parent.parent / "reports" / "v2"

SOURCE_FILES = {"webapp": FR_WEBAPP_FILE, "login": FR_LOGIN_FILE}


def _load_pipeline_config():
    concepts = load_concepts(CONFIG_DIR)
    glossary = ConceptGlossary(concepts)
    canonical_labels = load_canonical_labels(CONFIG_DIR)
    forbidden_pairs = load_forbidden_pairs(CONFIG_DIR)
    return glossary, canonical_labels, forbidden_pairs


def cmd_audit_v2(args: argparse.Namespace) -> None:
    glossary, canonical_labels, forbidden_pairs = _load_pipeline_config()

    fr_translations = load_translations(SOURCE_FILES[args.module])
    target_path = LANGUAGES_DIR / f"{args.lang}_{args.module}.json"
    target_translations = load_translations(target_path)

    nkeys = normalize_all(fr_translations, target_translations)
    classify_all(nkeys, glossary)

    structural_issues = validate_all_structure(nkeys, target_translations)
    semantic_issues = validate_semantics(
        nkeys, target_translations, glossary, args.lang, forbidden_pairs,
    )
    canonical_issues = validate_canonical_labels(target_translations, canonical_labels, args.lang)
    consistency_issues = validate_same_source_consistency(nkeys, target_translations)
    all_issues = structural_issues + semantic_issues + canonical_issues + consistency_issues

    from src.export import render_review_queue_markdown
    report = render_review_queue_markdown(all_issues, args.lang, args.module)

    REPORTS_V2_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_V2_DIR / f"{args.lang}_{args.module}.audit_v2.md"
    out_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\nWritten to: {out_path}")


def cmd_generate_v2(args: argparse.Namespace) -> None:
    glossary, canonical_labels, forbidden_pairs = _load_pipeline_config()

    fr_translations = load_translations(SOURCE_FILES[args.module])
    target_path = LANGUAGES_DIR / f"{args.lang}_{args.module}.json"
    target_translations = load_translations(target_path) if target_path.exists() else {}

    nkeys = normalize_all(fr_translations, target_translations)
    classify_all(nkeys, glossary)

    missing_nkeys = [k for k in nkeys if k.target is None]
    print(f"{len(missing_nkeys)} missing keys out of {len(nkeys)} total for {args.lang}_{args.module}")

    # Translation memory: bootstrap from whatever is already correctly
    # translated in this file, then check memory before ever calling the
    # LLM, so the same French text always reuses the same committed
    # translation instead of drifting between runs.
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    memory = TranslationMemory(MEMORY_PATH)
    added = memory.bootstrap_from_existing(args.lang, fr_translations, target_translations)
    if added:
        print(f"Translation memory: bootstrapped {added} entries from existing {args.lang} data")

    reused_from_memory: dict[str, str] = {}
    still_missing: list = []
    for nkey in missing_nkeys:
        cached = memory.lookup(args.lang, nkey.fr)
        if cached:
            reused_from_memory[nkey.key] = cached
        else:
            still_missing.append(nkey)
    if reused_from_memory:
        print(f"Translation memory: reused {len(reused_from_memory)} translations "
              f"without calling the LLM (identical French text already translated elsewhere)")

    if args.live:
        client = GeminiLLMClient(GCP_PROJECT_ID, GCP_LOCATION, GEMINI_MODEL)
    else:
        client = MockLLMClient()

    batches = build_batches(still_missing)
    print(f"Built {len(batches)} semantic batches for {len(still_missing)} genuinely new keys")

    all_new_translations: dict[str, str] = dict(reused_from_memory)
    all_review = {"blockers": [], "warnings": [], "suggestions": []}

    for batch in batches:
        prompt = build_prompt(batch, glossary, canonical_labels, target_language=args.lang)
        result = client.translate(prompt)
        all_new_translations.update(result.get("translations", {}))

        review = run_llm_review(batch, all_new_translations, args.lang, client)
        for k in ("blockers", "warnings", "suggestions"):
            all_review[k].extend(review.get(k, []))

    # Record every newly-translated (non-reused) key into memory for future runs
    fr_by_key = {k.key: k.fr for k in still_missing}
    for key, translation in all_new_translations.items():
        if key in reused_from_memory:
            continue
        fr_text = fr_by_key.get(key)
        if fr_text:
            memory.record(args.lang, fr_text, translation, key)
    memory.save()

    merged_for_validation = {**target_translations, **all_new_translations}
    structural_issues = validate_all_structure(nkeys, merged_for_validation)
    semantic_issues = validate_semantics(nkeys, merged_for_validation, glossary, args.lang, forbidden_pairs)
    canonical_issues = validate_canonical_labels(merged_for_validation, canonical_labels, args.lang)
    consistency_issues = validate_same_source_consistency(nkeys, merged_for_validation)

    # LLM review findings must land in the same human queue - previously these
    # were only printed as a count and then discarded, which meant a supervisor
    # reading review_queue.md would never see what the reviewer actually flagged.
    llm_issues = []
    for severity, key_name in (("BLOCKER", "blockers"), ("WARNING", "warnings"), ("REVIEW", "suggestions")):
        for entry in all_review[key_name]:
            key_part = entry.split(":", 1)[0].strip() if ":" in entry else "unknown_key"
            llm_issues.append(ValidationIssue(key_part, severity, entry, "llm_review"))

    paths = export_results(
        target_translations, all_new_translations,
        structural_issues + semantic_issues + canonical_issues + consistency_issues + llm_issues,
        REPORTS_V2_DIR, args.lang, args.module,
    )
    print("Exported:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
    print("\nLLM review summary:")
    for k in ("blockers", "warnings", "suggestions"):
        print(f"  {k}: {len(all_review[k])}")


def cmd_sync_v2(args: argparse.Namespace) -> None:
    """
    Direct replacement for scripts/03_translation_pipeline.py's
    sync_missing_keys(). That function calls translate_large_json(), which
    internally chunks into arbitrary CHUNK_SIZE (200) blocks with no
    glossary awareness - exactly what the technical lead's document says
    to stop doing.

    This does the same job (find missing keys per language file, translate
    them, write back into the same file in place) but routes through the
    full V2 pipeline: normalize -> classify -> semantic batch -> closed
    prompt -> translate -> structural validation -> semantic validation ->
    export. It only touches files matching the clean `{lang}_{module}.json`
    naming convention - see reports/v2/cross_language_findings.md for the
    files that don't follow that convention and need manual handling.
    """
    glossary, canonical_labels, forbidden_pairs = _load_pipeline_config()
    client = GeminiLLMClient(GCP_PROJECT_ID, GCP_LOCATION, GEMINI_MODEL) if args.live else MockLLMClient()

    if not args.live:
        print("=" * 70)
        print("MOCK MODE: no --live flag passed.")
        print("Real files in languages/ will NOT be modified.")
        print("Synced output will be written to reports/v2/*.synced_mock.json")
        print("for you to review. Re-run with --live to actually update your")
        print("real language files with real Gemini translations.")
        print("=" * 70)

    updated_files = []
    skipped_files = []

    for path in sorted(LANGUAGES_DIR.glob("*.json")):
        name = path.stem
        parts = name.split("_", 1)
        if len(parts) != 2 or parts[1] not in ("webapp", "login"):
            skipped_files.append(path.name)
            continue

        lang_code, module = parts
        if module not in SOURCE_FILES:
            skipped_files.append(path.name)
            continue

        fr_translations = load_translations(SOURCE_FILES[module])
        target_translations = load_translations(path)

        nkeys = normalize_all(fr_translations, target_translations)
        classify_all(nkeys, glossary)
        missing_nkeys = [k for k in nkeys if k.target is None]

        if not missing_nkeys:
            print(f"{path.name}: no missing keys, skipped")
            continue

        batches = build_batches(missing_nkeys)
        new_translations: dict[str, str] = {}
        for batch in batches:
            prompt = build_prompt(batch, glossary, canonical_labels, target_language=lang_code)
            result = client.translate(prompt)
            new_translations.update(result.get("translations", {}))

        merged = {**target_translations, **new_translations}
        structural_issues = validate_all_structure(nkeys, merged)
        semantic_issues = validate_semantics(nkeys, merged, glossary, lang_code, forbidden_pairs)
        n_issues = len(structural_issues) + len(semantic_issues)

        if args.live:
            backup_path = path.with_suffix(path.suffix + ".bak")
            if not backup_path.exists():
                save_json({"translations": target_translations}, backup_path)
            save_json({"translations": merged}, path)
            print(f"{path.name}: synced {len(new_translations)} missing keys "
                  f"(backup saved to {backup_path.name}), {n_issues} validation issues to review")
        else:
            mock_out = REPORTS_V2_DIR / f"{lang_code}_{module}.synced_mock.json"
            save_json({"translations": merged}, mock_out)
            print(f"{path.name}: [MOCK] would sync {len(new_translations)} missing keys, "
                  f"{n_issues} validation issues -> preview written to {mock_out.name} (real file untouched)")

        updated_files.append((path.name, len(new_translations), n_issues))

    print("\n=== sync-v2 summary ===")
    print(f"Updated: {len(updated_files)} files")
    for name, n_new, n_issues in updated_files:
        print(f"  {name}: +{n_new} keys, {n_issues} issues flagged")
    if skipped_files:
        print(f"Skipped (non-standard filename, not {{lang}}_{{module}}.json): {len(skipped_files)} files")
        for name in skipped_files:
            print(f"  {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Omniscol semantic translation pipeline (V2)")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit-v2", help="Structural + semantic validation only, no LLM")
    audit.add_argument("--lang", required=True)
    audit.add_argument("--module", required=True, choices=list(SOURCE_FILES.keys()))

    gen = sub.add_parser("generate-v2", help="Full pipeline for missing keys")
    gen.add_argument("--lang", required=True)
    gen.add_argument("--module", required=True, choices=list(SOURCE_FILES.keys()))
    gen.add_argument("--live", action="store_true", help="Use real Gemini/Vertex AI instead of the mock client")
    gen.add_argument("--mock", action="store_true", default=True, help=argparse.SUPPRESS)

    sync = sub.add_parser("sync-v2", help="Replace V1's 200-key chunker: sync all missing keys via the semantic pipeline")
    sync.add_argument("--live", action="store_true", help="Use real Gemini/Vertex AI instead of the mock client")

    args = parser.parse_args()

    if args.command == "audit-v2":
        cmd_audit_v2(args)
    elif args.command == "generate-v2":
        cmd_generate_v2(args)
    elif args.command == "sync-v2":
        cmd_sync_v2(args)


if __name__ == "__main__":
    main()
