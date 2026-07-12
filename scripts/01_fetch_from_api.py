import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import argparse
import json
from pathlib import Path
import requests

from config import BASE_URL, OMNISCOL_TOKEN, RAW_DIR

DEFAULT_ENDPOINTS = {
    "webapp": "/i18n/{lang}/webapp",
    "login": "/i18n/{lang}/login",
    "portal": "/i18n/{lang}/portal",
    "portal_multi": "/i18n/{lang}/portal_multi",
}


def build_headers() -> dict:
    headers = {"Accept": "application/json"}
    if OMNISCOL_TOKEN:
        headers["Authorization"] = f"Bearer {OMNISCOL_TOKEN}"
    return headers


def fetch_json(endpoint: str, params: dict | None = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    response = requests.get(url, headers=build_headers(), params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def save_json(data: dict, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Omniscol translation JSON files from API.")
    parser.add_argument("--lang", required=True, help="Language code, for example fr, en, nl, kk, pl")
    parser.add_argument("--modules", nargs="+", default=["webapp", "login"],
                        choices=list(DEFAULT_ENDPOINTS.keys()), help="Modules to fetch")
    parser.add_argument("--with-languages", action="store_true", help="Pass with_languages=true")
    parser.add_argument("--country", default=None, help="Optional country parameter, e.g. fr")
    args = parser.parse_args()

    params = {}
    if args.with_languages:
        params["with_languages"] = "true"
    if args.country:
        params["country"] = args.country

    for module in args.modules:
        endpoint = DEFAULT_ENDPOINTS[module].format(lang=args.lang)
        data = fetch_json(endpoint, params=params or None)
        out = RAW_DIR / f"{args.lang}_{module}.json"
        save_json(data, out)
        print(f"Saved {module}: {out}")


if __name__ == "__main__":
    main()
