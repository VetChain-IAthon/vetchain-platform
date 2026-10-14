"""docs/openapi.json está al día. Si falla: python -m scripts.export_openapi"""
import json
from pathlib import Path

from app.main import app


def test_openapi_json_is_up_to_date():
    saved = json.loads(Path("docs/openapi.json").read_text(encoding="utf-8"))
    assert saved == json.loads(json.dumps(app.openapi())), "Ejecuta: python -m scripts.export_openapi"
