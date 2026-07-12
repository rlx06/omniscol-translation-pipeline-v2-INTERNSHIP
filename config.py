from pathlib import Path

# API
BASE_URL = "https://sandboxai.omniscol.com"

import os
OMNISCOL_TOKEN = os.getenv("OMNISCOL_TOKEN", "")

# folders
RAW_DIR = Path("data/raw")
SOURCE_DIR = Path("data/source")
LANGUAGES_DIR = Path("languages")
REPORTS_DIR = Path("data/reports")

# source files
FR_WEBAPP_FILE = SOURCE_DIR / "fr_webapp.json"
FR_LOGIN_FILE = SOURCE_DIR / "fr_login.json"
GLOSSARY_FILE = SOURCE_DIR / "Glossary.md"

# pipeline settings
CHUNK_SIZE = 200

# AI config
GCP_PROJECT_ID = "erudite-bonbon-457709-p9"
GCP_LOCATION = "europe-west4"
GEMINI_MODEL = "gemini-2.5-flash"