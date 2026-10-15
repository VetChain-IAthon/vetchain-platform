"""Descarga los artefactos privados del pronóstico desde un repositorio privado de GitHub (build de Render).

Variables: FORECAST_MODELS_TOKEN (token de solo lectura del repo), FORECAST_MODELS_REPO (por defecto
VetChain-IAthon/vetchain-models), FORECAST_MODELS_REF (rama o etiqueta, por defecto main) y FORECAST_MODELS_DIR
(destino, por defecto models/forecast). Sin token no descarga nada y no falla: la API sigue funcionando y el pronóstico
responde 503 hasta instalar los modelos.

Uso: python -m scripts.fetch_forecast_models
"""
import io
import os
import sys
import tarfile
import urllib.request
from pathlib import Path

ALLOWED_SUFFIXES = {".joblib", ".json", ".csv"}


def main() -> int:
    token = os.environ.get("FORECAST_MODELS_TOKEN", "").strip()
    if not token:
        print("FORECAST_MODELS_TOKEN no está definido: no se descargan los modelos de pronóstico.")
        return 0
    repo = os.environ.get("FORECAST_MODELS_REPO", "VetChain-IAthon/vetchain-models")
    ref = os.environ.get("FORECAST_MODELS_REF", "main")
    target = Path(os.environ.get("FORECAST_MODELS_DIR") or "models/forecast")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/tarball/{ref}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "vetchain-build"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except Exception as exc:  # el mensaje nunca incluye el token
        print(f"No se pudieron descargar los modelos de {repo}@{ref}: {exc}", file=sys.stderr)
        return 1

    target.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = Path(member.name).name  # aplana la carpeta raíz del tarball; ignora subcarpetas y rutas raras
            if not member.isfile() or Path(name).suffix not in ALLOWED_SUFFIXES or member.name.count("/") != 1:
                continue
            source = archive.extractfile(member)
            if source is None:
                continue
            (target / name).write_bytes(source.read())
            count += 1
    if not any(target.glob("extratrees_*.joblib")):
        print(f"El repositorio {repo}@{ref} no tiene modelos extratrees_*.joblib.", file=sys.stderr)
        return 1
    print(f"Modelos de pronóstico instalados en {target}: {count} archivos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
