"""
LLM client abstraction.

The rest of the pipeline never calls Gemini/Vertex directly - it calls
this interface. That means:
  - `GeminiLLMClient` reuses the exact same auth/config as V1
    (config.py: GCP_PROJECT_ID, GCP_LOCATION, GEMINI_MODEL), so it works
    the moment this runs with real Omniscol/GCP credentials.
  - `MockLLMClient` lets every other stage (batching, validation, export)
    be developed and tested right now, without API access, and without
    ever pretending a fake API call happened.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def translate(self, prompt: str) -> dict:
        """Must return {'translations': {...}, 'flags': {...}}."""

    @abstractmethod
    def review(self, prompt: str) -> dict:
        """Must return {'blockers': [...], 'warnings': [...], 'suggestions': [...]}."""


class GeminiLLMClient(LLMClient):
    """Thin wrapper around the same google-genai / Vertex AI call V1 already uses."""

    def __init__(self, project_id: str, location: str, model: str):
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai is not installed. Run: pip install google-genai --break-system-packages"
            ) from exc

        if not project_id:
            raise RuntimeError("GCP_PROJECT_ID is not configured in config.py")

        self._genai = genai
        self._types = types
        self._client = genai.Client(
            vertexai=True,
            project=project_id,
            location=location,
            http_options=types.HttpOptions(api_version="v1"),
        )
        self._model = model

    def _call(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        return response.candidates[0].content.parts[0].text

    def translate(self, prompt: str) -> dict:
        raw = self._call(prompt)
        parsed = json.loads(raw)
        parsed.setdefault("translations", {})
        parsed.setdefault("flags", {})
        return parsed

    def review(self, prompt: str) -> dict:
        raw = self._call(prompt)
        parsed = json.loads(raw)
        parsed.setdefault("blockers", [])
        parsed.setdefault("warnings", [])
        parsed.setdefault("suggestions", [])
        return parsed


class MockLLMClient(LLMClient):
    """
    Deterministic stand-in used for local development, tests, and this
    demo - it does NOT produce real translations. Every output is prefixed
    so it can never be mistaken for genuine model output if it accidentally
    ends up in an export.
    """

    MOCK_PREFIX = "[MOCK-TRANSLATION] "

    def translate(self, prompt: str) -> dict:
        # Extract the source payload back out of the prompt to keep this
        # deterministic and dependency-free (no LLM call at all).
        marker = "Keys to translate"
        start = prompt.find("{", prompt.find(marker))
        end = prompt.rfind("}\n\nOutput format")
        try:
            source = json.loads(prompt[start:end + 1])
        except (ValueError, json.JSONDecodeError):
            source = {}
        translations = {k: f"{self.MOCK_PREFIX}{v}" for k, v in source.items()}
        return {"translations": translations, "flags": {}}

    def review(self, prompt: str) -> dict:
        return {"blockers": [], "warnings": [], "suggestions": [
            "MockLLMClient does not perform real semantic review - "
            "wire up GeminiLLMClient before trusting this stage."
        ]}
