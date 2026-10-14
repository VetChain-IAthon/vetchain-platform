"""Genera docs/openapi.json desde la app. tests/test_openapi.py falla si quedó desactualizado.

Uso: python -m scripts.export_openapi
"""
import json
from pathlib import Path

from app.main import app

OUTPUT = Path("docs/openapi.json")


def build_openapi() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUTPUT.write_text(build_openapi(), encoding="utf-8")
    print(f"OpenAPI escrito en {OUTPUT}")


if __name__ == "__main__":
    main()
