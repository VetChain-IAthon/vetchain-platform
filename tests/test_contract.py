"""Las rutas de la app coinciden con docs/endpoints.md (tablas | Método | Ruta | ...)."""
import re
from pathlib import Path

from app.main import API_PREFIX, app

ROW = re.compile(r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*(/\S*)\s*\|", re.MULTILINE)


def _documented() -> set[tuple[str, str]]:
    text = Path("docs/endpoints.md").read_text(encoding="utf-8")
    return {(method, path if path == "/health" else API_PREFIX + path) for method, path in ROW.findall(text)}


def _implemented() -> set[tuple[str, str]]:
    paths = app.openapi()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() for method in operations}


def test_routes_match_endpoints_md():
    documented, implemented = _documented(), _implemented()
    assert documented - implemented == set(), "En endpoints.md pero no en la app"
    assert implemented - documented == set(), "En la app pero no en endpoints.md"
