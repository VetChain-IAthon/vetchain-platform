"""Gemini redacta sobre cifras agregadas del pronóstico, sin datos de clientes."""
from functools import lru_cache

from google import genai
from google.genai import types


@lru_cache(maxsize=1)
def _client(api_key: str, timeout_seconds: int) -> genai.Client:
    retry = types.HttpRetryOptions(attempts=3, initial_delay=1, max_delay=4,
                                   http_status_codes=[429, 500, 503, 504])
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=timeout_seconds * 1000, retry_options=retry))


class GeminiForecastTextGenerator:
    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("Gemini no está configurado.")
        response = _client(self.api_key, self.timeout_seconds).models.generate_content(
            model=self.model, contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return (response.text or "").strip()
