"""
File loading helpers.

Reuses the same file layout as V1 (config.py: FR_WEBAPP_FILE, FR_LOGIN_FILE,
LANGUAGES_DIR) so V2 runs against the exact same data the pipeline already
fetches from the Omniscol API - no new source-of-truth is introduced.
"""
from __future__ import annotations

import json
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(data: dict, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_translations(path: Path) -> dict[str, str]:
    """Omniscol JSON files wrap the flat key->value map inside a 'translations' key."""
    data = load_json(path)
    return data.get("translations", data)


def load_concepts(config_dir: Path) -> dict:
    concepts = load_json(Path(config_dir) / "concepts.json")
    concepts.pop("_comment", None)
    return concepts


def load_canonical_labels(config_dir: Path) -> dict:
    labels = load_json(Path(config_dir) / "canonical_labels.json")
    labels.pop("_comment", None)
    return labels


def load_forbidden_pairs(config_dir: Path) -> list[tuple[str, str]]:
    data = load_json(Path(config_dir) / "forbidden_terms.json")
    return [tuple(pair) for pair in data.get("pairs", [])]
