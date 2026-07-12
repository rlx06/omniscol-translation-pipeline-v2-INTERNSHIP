import argparse
import json
import logging
import random
import re
import time
from pathlib import Path

from config import (
    CHUNK_SIZE,
    FR_LOGIN_FILE,
    FR_WEBAPP_FILE,
    GCP_LOCATION,
    GCP_PROJECT_ID,
    GEMINI_MODEL,
    GLOSSARY_FILE,
    LANGUAGES_DIR,
)

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None


# -----------------------------
# Basic settings
# -----------------------------
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 2
MAX_BACKOFF_SECONDS = 30
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "translation_pipeline.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)

PLACEHOLDER_PATTERNS = [
    r"\{[^{}]+\}",       # {name}
    r"\{\{[^{}]+\}\}",   # {{name}}
    r"%s",
    r"%d",
    r"%f",
]


# -----------------------------
# Gemini / Vertex setup
# -----------------------------
def require_genai() -> tuple:
    if not genai or not types or not GCP_PROJECT_ID:
        raise RuntimeError(
            "Gemini/Vertex AI is not configured. "
            "Check google-genai installation and config.py values."
        )

    client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT_ID,
        location=GCP_LOCATION,
        http_options=types.HttpOptions(api_version="v1"),
    )
    return client, types


# -----------------------------
# File helpers
# -----------------------------
def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_glossary() -> str:
    return GLOSSARY_FILE.read_text(encoding="utf-8")


def split_json(translations: dict, chunk_size: int = CHUNK_SIZE):
    items = list(translations.items())
    for i in range(0, len(items), chunk_size):
        yield dict(items[i:i + chunk_size])


# -----------------------------
# Validation helpers
# -----------------------------
def extract_placeholders(text: str) -> set[str]:
    found = set()
    if not isinstance(text, str):
        return found

    for pattern in PLACEHOLDER_PATTERNS:
        matches = re.findall(pattern, text)
        found.update(matches)

    return found

def contains_french_leak(source_text: str, translated_text: str) -> bool:
    if not isinstance(source_text, str) or not isinstance(translated_text, str):
        return False

    source_clean = source_text.strip().lower()
    translated_clean = translated_text.strip().lower()

    if len(source_clean) <= 4:
        return False

    # Skip values that are legitimately untranslatable
    SKIP_TRANSLATION_PATTERNS = [
        r"^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$",          # email address
        r"^https?://",                                  # URL
        r"^[A-Z]+$",                                    # all-caps acronym (JSON, HTML...)
        r"^\{[^{}]+\}$",                                # pure single placeholder {name}
        r"^[\d\s\-+().]+$",                             # phone / pure digits
        r"^[\w\-]+\.(pdf|csv|xlsx|json|xml|png|jpg)$",
        r"^[A-Za-z0-9_\-\.]+$",   # single technical word / acronym (JSON, PDF, CSV, OAuth...)# simple filename
    ]

    for pattern in SKIP_TRANSLATION_PATTERNS:
        if re.match(pattern, source_text.strip()):
            return False

        # Skip if value looks like a technical filename pattern
        # e.g. '{date}_edt_toutes_classes.pdf' — even with French words, filenames stay as-is
        if re.search(r"\.(pdf|csv|xlsx|json|xml|png|jpg|docx)$", source_text.strip().lower()):
            return False

        # Skip if the value is ONLY placeholders and non-alphabetic characters
        # e.g. '{first_name} {last_name}' or '{date}_edt_{class}.pdf'
        placeholder_stripped = re.sub(r"\{[^{}]+\}", "", source_text)
        placeholder_stripped = re.sub(r"[_\-\.\s/]", "", placeholder_stripped)
        if placeholder_stripped.strip() == "":
            return False

        return source_clean == translated_clean


def validate_translation_chunk(source_chunk: dict, translated_chunk: dict) -> list[str]:
    errors = []

    source_keys = set(source_chunk.keys())
    translated_keys = set(translated_chunk.keys())

    missing_keys = source_keys - translated_keys
    extra_keys = translated_keys - source_keys

    if missing_keys:
        errors.append(f"Missing keys: {sorted(missing_keys)}")
    if extra_keys:
        errors.append(f"Extra keys: {sorted(extra_keys)}")

    for key, source_value in source_chunk.items():
        translated_value = translated_chunk.get(key)

        if not isinstance(translated_value, str):
            errors.append(f"{key}: translated value is not a string")
            continue

        if not translated_value.strip():
            errors.append(f"{key}: translated value is empty")

        source_placeholders = extract_placeholders(source_value)
        translated_placeholders = extract_placeholders(translated_value)

        if source_placeholders != translated_placeholders:
            errors.append(
                f"{key}: placeholder mismatch | "
                f"source={sorted(source_placeholders)} | "
                f"target={sorted(translated_placeholders)}"
            )

        if contains_french_leak(source_value, translated_value):
            errors.append(f"{key}: translated value appears unchanged from French source")

    return errors


def save_validation_report(chunk_index: int, errors: list[str], chunk_data: dict) -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    report_path = reports_dir / f"chunk_{chunk_index}_validation.md"
    lines = [
        f"# Validation report for chunk {chunk_index}",
        "",
        "## Errors",
    ]
    lines.extend([f"- {error}" for error in errors])
    lines.append("")
    lines.append("## Source chunk")
    lines.append("```json")
    lines.append(json.dumps(chunk_data, ensure_ascii=False, indent=2))
    lines.append("```")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.warning(f"Saved validation report: {report_path}")


# -----------------------------
# Retry helpers
# -----------------------------
def is_retryable_error(exc: Exception) -> bool:
    error_text = str(exc).lower()

    retryable_markers = [
        "429",
        "resource_exhausted",
        "503",
        "unavailable",
        "deadline_exceeded",
        "timeout",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
    ]

    return any(marker in error_text for marker in retryable_markers)


def sleep_with_backoff(attempt_number: int) -> None:
    sleep_seconds = min(BACKOFF_BASE_SECONDS ** attempt_number, MAX_BACKOFF_SECONDS)
    jitter = random.uniform(0, 1.0)
    total_sleep = sleep_seconds + jitter
    logger.info(f"Waiting {total_sleep:.2f}s before retry")
    time.sleep(total_sleep)


# -----------------------------
# Translation
# -----------------------------
def translate_chunk(client, types_module, chunk: dict, target_language: str, glossary: str) -> dict:
    prompt = f"""
You are a professional localization translator.

Task:
Translate the following JSON values from French to {target_language}.

Strict rules:
- Keep all keys exactly identical
- Translate only the values
- Preserve placeholders exactly, such as {{name}}, %s, %d, and HTML tags
- Preserve punctuation, spacing, and line breaks where possible
- Do not remove keys
- Do not add keys
- Do not explain anything
- Return valid JSON only
- Follow the glossary strictly and consistently

Glossary:
{glossary}

JSON:
{json.dumps(chunk, ensure_ascii=False)}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types_module.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        ),
    )

    raw_text = response.candidates[0].content.parts[0].text
    return json.loads(raw_text)


def translate_large_json(source_json: dict, target_language: str, glossary: str) -> dict:
    client, types_module = require_genai()
    source = source_json.get("translations", source_json)
    final = {}

    chunks = list(split_json(source))
    total_chunks = len(chunks)

    logger.info(f"Splitting into {total_chunks} chunks for {target_language}")

    for i, chunk in enumerate(chunks, start=1):
        logger.info(f"Translating chunk {i}/{total_chunks}")

        chunk_success = False

        for attempt in range(1, MAX_RETRIES + 1):
            start_time = time.time()

            try:
                translated = translate_chunk(client, types_module, chunk, target_language, glossary)

                validation_errors = validate_translation_chunk(chunk, translated)
                if validation_errors:
                    save_validation_report(i, validation_errors, chunk)

                    if attempt == MAX_RETRIES:
                        raise RuntimeError(
                            f"Chunk {i} failed validation after {MAX_RETRIES} attempts: "
                            + " | ".join(validation_errors[:5])
                        )

                    logger.warning(
                        f"Chunk {i} validation failed on attempt {attempt}/{MAX_RETRIES}. Retrying."
                    )
                    sleep_with_backoff(attempt)
                    continue

                final.update(translated)

                elapsed = time.time() - start_time
                logger.info(f"Chunk {i}/{total_chunks} translated in {elapsed:.2f}s")

                chunk_success = True
                break

            except Exception as exc:
                elapsed = time.time() - start_time

                if not is_retryable_error(exc):
                    logger.error(
                        f"Non-retryable error on chunk {i}/{total_chunks} after {elapsed:.2f}s: {exc}"
                    )
                    raise RuntimeError(f"Chunk {i} failed with non-retryable error: {exc}") from exc

                if attempt == MAX_RETRIES:
                    logger.error(
                        f"Chunk {i}/{total_chunks} failed after {MAX_RETRIES} attempts: {exc}"
                    )
                    raise RuntimeError(f"Chunk {i} failed after retries: {exc}") from exc

                logger.warning(
                    f"Retrying chunk {i}/{total_chunks} "
                    f"(attempt {attempt}/{MAX_RETRIES}) after {elapsed:.2f}s: {exc}"
                )
                sleep_with_backoff(attempt)

        if not chunk_success:
            raise RuntimeError(f"Chunk {i} failed and could not be translated.")

    return final


# -----------------------------
# Main commands
# -----------------------------
def generate_language(lang_code: str, lang_name: str) -> None:
    logger.info(f"Starting language generation for {lang_code} ({lang_name})")

    glossary = load_glossary()
    fr_webapp = load_json(FR_WEBAPP_FILE)
    fr_login = load_json(FR_LOGIN_FILE)

    webapp_translation = translate_large_json(fr_webapp, lang_name, glossary)
    login_translation = translate_large_json(fr_login, lang_name, glossary)

    webapp_path = LANGUAGES_DIR / f"{lang_code}_webapp.json"
    login_path = LANGUAGES_DIR / f"{lang_code}_login.json"

    save_json({"translations": webapp_translation}, webapp_path)
    save_json({"translations": login_translation}, login_path)

    logger.info(f"Saved: {webapp_path}")
    logger.info(f"Saved: {login_path}")
    logger.info(f"Generated {lang_code} language files")


def sync_missing_keys(language_name_map: dict[str, str]) -> None:
    logger.info("Starting sync-missing-keys")

    glossary = load_glossary()
    fr_webapp = load_json(FR_WEBAPP_FILE)["translations"]
    fr_login = load_json(FR_LOGIN_FILE)["translations"]

    for path in LANGUAGES_DIR.glob("*.json"):
        data = load_json(path)["translations"]
        source = fr_webapp if "webapp" in path.name else fr_login
        missing = {k: v for k, v in source.items() if k not in data}

        if not missing:
            logger.info(f"No missing keys in {path.name}")
            continue

        lang_code = path.name.split("_")[0]
        target_language = language_name_map.get(lang_code, lang_code)

        logger.info(f"Syncing {path.name}: {len(missing)} keys -> {target_language}")

        translated = translate_large_json({"translations": missing}, target_language, glossary)
        data.update(translated)
        save_json({"translations": data}, path)

        logger.info(f"Updated file: {path}")


def audit_translations() -> None:
    logger.info("Starting audit")

    client, _types_module = require_genai()
    glossary = load_glossary()

    for path in LANGUAGES_DIR.glob("*.json"):
        data = load_json(path)["translations"]

        prompt = f"""
Audit the following translations against the glossary.

Return markdown with:
- wrong terms
- inconsistent translations
- suggestions

Glossary:
{glossary}

Translations:
{json.dumps(data, ensure_ascii=False)[:12000]}
"""

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        report_path = path.with_suffix(".audit.md")
        report_path.write_text(response.text, encoding="utf-8")
        logger.info(f"Saved audit: {report_path}")


# -----------------------------
# CLI
# -----------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Omniscol translation pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-language")
    gen.add_argument("lang_code")
    gen.add_argument("lang_name")

    sync = sub.add_parser("sync-missing-keys")
    sync.add_argument("--map", default="{}", help='JSON dict, e.g. {"pl": "Polish"}')

    sub.add_parser("audit")

    args = parser.parse_args()

    if args.command == "generate-language":
        generate_language(args.lang_code, args.lang_name)
    elif args.command == "sync-missing-keys":
        sync_missing_keys(json.loads(args.map))
    elif args.command == "audit":
        audit_translations()


if __name__ == "__main__":
    main()