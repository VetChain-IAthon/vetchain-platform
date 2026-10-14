"""Prepara Neon con migraciones, CSV y usuarios iniciales opcionales.

Sin --apply solo valida la configuración. La URL y las credenciales de usuarios
deben estar exportadas en el entorno; no se toman del .env local.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

from app.core.config import Settings
from app.infrastructure.loaders.defontana_csv import find_files


ROOT = Path(__file__).resolve().parents[1]
SEED_KEYS = (
    "SEED_MANAGER_EMAIL", "SEED_MANAGER_PASSWORD", "SEED_MANAGER_NAME", "SEED_MANAGER_PHONE",
    "SEED_SALESPERSON_EMAIL", "SEED_SALESPERSON_PASSWORD", "SEED_SALESPERSON_NAME",
    "SEED_SALESPERSON_PHONE", "SEED_SALESPERSON_CODE",
)


def validate_neon_url(value: str | None) -> None:
    """Exige una conexión directa y cifrada a Neon indicada explícitamente."""
    if not value:
        raise ValueError("Define DATABASE_URL en el entorno con la conexión directa de Neon.")
    parts = urlsplit(value)
    if parts.scheme not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise ValueError("DATABASE_URL debe ser una conexión PostgreSQL de Neon.")
    host = parts.hostname or ""
    if not host.endswith(".neon.tech"):
        raise ValueError("DATABASE_URL no apunta a Neon; se detuvo antes de escribir datos.")
    if host.split(".", 1)[0].endswith("-pooler"):
        raise ValueError("Usa la conexión directa de Neon, sin '-pooler', para las migraciones y la carga.")
    if not parts.username or not parts.password or not parts.path.strip("/"):
        raise ValueError("DATABASE_URL debe incluir usuario, contraseña y base de datos.")
    if parse_qs(parts.query).get("sslmode", [""])[0] not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("DATABASE_URL debe exigir TLS (sslmode=require o superior).")


def validate_seed_environment(environment: dict[str, str]) -> None:
    """Evita reutilizar por accidente las credenciales del .env local."""
    required = ["SEED_MANAGER_EMAIL", "SEED_MANAGER_PASSWORD"]
    if environment.get("SEED_SALESPERSON_EMAIL"):
        required += ["SEED_SALESPERSON_PASSWORD", "SEED_SALESPERSON_CODE"]
    missing = [key for key in required if not environment.get(key)]
    if missing:
        raise ValueError("Define en el entorno las variables para usuarios iniciales: " + ", ".join(missing))


def seed_environment(env_file: Path | None) -> dict[str, str]:
    """Lee solo las credenciales SEED_* de un archivo indicado expresamente."""
    environment = dict(os.environ)
    if env_file is None:
        return environment
    if not env_file.is_file():
        raise FileNotFoundError(f"No existe el archivo de credenciales {env_file}.")
    configured = Settings(_env_file=env_file)
    for key in SEED_KEYS:
        environment.setdefault(key, getattr(configured, key.lower()))
    return environment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=ROOT / "data", help="Carpeta de los siete CSV")
    parser.add_argument("--apply", action="store_true", help="Ejecuta migraciones y carga de datos")
    parser.add_argument("--seed-users", action="store_true", help="Crea los usuarios iniciales después de cargar los CSV")
    parser.add_argument("--seed-env-file", type=Path, help="Archivo local con SEED_*; requiere --seed-users")
    args = parser.parse_args(argv)
    if args.seed_env_file and not args.seed_users:
        parser.error("--seed-env-file requiere --seed-users")

    try:
        validate_neon_url(os.environ.get("DATABASE_URL"))
        csv_dir = args.csv_dir.resolve()
        files = find_files(csv_dir)
        child_environment = seed_environment(args.seed_env_file)
        if args.seed_users:
            validate_seed_environment(child_environment)
    except (ValueError, FileNotFoundError) as error:
        parser.exit(2, f"Error: {error}\n")

    print(f"Configuración válida: {len(files)} CSV encontrados para la conexión directa de Neon.", flush=True)
    if not args.apply:
        print("No se escribió en la base de datos. Ejecuta con --apply para migrar y cargar.")
        return 0

    commands = [
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        [sys.executable, "-m", "scripts.load_csv", str(csv_dir)],
    ]
    if args.seed_users:
        commands.append([sys.executable, "-m", "scripts.seed_users"])
    for key in SEED_KEYS:
        child_environment.setdefault(key, "")
    for command in commands:
        subprocess.run(command, cwd=ROOT, env=child_environment, check=True)
    print("Neon preparado. Revisa el reporte de carga y verifica los conteos en la base.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
