"""Crea el usuario de gerencia (administrador) y el de vendedor por defecto. Se puede repetir: no duplica.

Uso:
  python -m scripts.seed_users            usa las credenciales SEED_* de .env (o del entorno)
  python -m scripts.seed_users --random   genera nombre, correo, celular y contraseña aleatorios, elige al azar un
                                          vendedor activo de Defontana, los guarda en .env y crea los usuarios

Variables: SEED_MANAGER_{EMAIL,PASSWORD,NAME,PHONE} y SEED_SALESPERSON_{EMAIL,PASSWORD,NAME,PHONE,CODE}.
Correr después de `alembic upgrade head` y de cargar los CSV (el vendedor necesita su código en salespeople).
"""
import re
import secrets
import sys
import unicodedata
from pathlib import Path

from sqlalchemy import select

from app.core.config import Settings, settings
from app.core.database import SessionLocal
from app.core.domain import ConflictError, DomainError
from app.infrastructure.db.source_models import Salesperson
from app.modules.auth.application.commands import CreateUserCommand
from app.modules.auth.interface.dependencies import build_create_user

ENV_FILE = Path(".env")
EMAIL_DOMAIN = "mederi.local"
NOT_A_PERSON = {"000", "001"}  # NO DEFINIDO y OFICINA

FIRST_NAMES = [
    "Lucía", "Mateo", "Valeria", "Diego", "Camila", "Sebastián", "Daniela", "Andrés", "Mariana", "Joaquín",
    "Fernanda", "Gabriel", "Rosa", "Luis", "Carmen", "Jorge", "Patricia", "Ricardo", "Milagros", "César",
]
LAST_NAMES = [
    "Quispe", "Flores", "Huamán", "Mamani", "Rojas", "Sánchez", "García", "Torres", "Chávez", "Vargas",
    "Mendoza", "Castillo", "Ramírez", "Paredes", "Gutiérrez", "Salazar", "Cáceres", "Ccori", "Rivera", "Espinoza",
]


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def random_profile(taken_emails: set[str]) -> dict[str, str]:
    while True:
        first, last, second = secrets.choice(FIRST_NAMES), secrets.choice(LAST_NAMES), secrets.choice(LAST_NAMES)
        email = f"{_ascii(first)}.{_ascii(last)}{secrets.randbelow(90) + 10}@{EMAIL_DOMAIN}"
        if email not in taken_emails:
            break
    return {
        "NAME": f"{first} {last} {second}",
        "EMAIL": email,
        "PHONE": "9" + "".join(str(secrets.randbelow(10)) for _ in range(8)),
        "PASSWORD": secrets.token_urlsafe(12),
    }


def _active_salesperson_codes() -> list[str]:
    with SessionLocal() as db:
        codes = db.scalars(select(Salesperson.code).where(Salesperson.is_active.is_(True)).order_by(Salesperson.code))
        return [code for code in codes if code not in NOT_A_PERSON]


def write_env(values: dict[str, str]) -> None:
    """Reemplaza (o agrega) las variables SEED_* en .env sin tocar el resto."""
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    for key, value in values.items():
        line = f"{key}={value}"
        if re.search(rf"^{key}=.*$", text, flags=re.MULTILINE):
            text = re.sub(rf"^{key}=.*$", line, text, flags=re.MULTILINE)
        else:
            text = text.rstrip("\n") + f"\n{line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    ENV_FILE.chmod(0o600)


def generate_random() -> Settings:
    codes = _active_salesperson_codes()
    if not codes:
        sys.exit("No hay vendedores activos en salespeople: carga primero los CSV (python -m scripts.load_csv).")
    manager = random_profile(set())
    salesperson = random_profile({manager["EMAIL"]})
    values = {f"SEED_MANAGER_{key}": value for key, value in manager.items()}
    values |= {f"SEED_SALESPERSON_{key}": value for key, value in salesperson.items()}
    values["SEED_SALESPERSON_CODE"] = secrets.choice(codes)
    write_env(values)
    print(f"Datos aleatorios guardados en {ENV_FILE} (SEED_*).")
    return Settings()


def _seed(command: CreateUserCommand) -> None:
    with SessionLocal() as db:
        try:
            user = build_create_user(db).execute(command)
            print(f"Creado {user.role.value}: {user.full_name} <{user.email}> (id {user.id})")
        except ConflictError:
            print(f"Ya existe {command.email}: no se cambia.")
        except DomainError as error:
            sys.exit(f"No se pudo crear {command.email}: {error.message}")


def main() -> None:
    config = generate_random() if "--random" in sys.argv[1:] else settings
    if not config.seed_manager_email or not config.seed_manager_password:
        sys.exit("Faltan SEED_MANAGER_EMAIL y SEED_MANAGER_PASSWORD (o usa --random).")
    _seed(CreateUserCommand(
        config.seed_manager_email, config.seed_manager_name or "Gerencia", "manager",
        config.seed_manager_password, config.seed_manager_phone or None,
    ))
    if config.seed_salesperson_email:
        _seed(CreateUserCommand(
            config.seed_salesperson_email, config.seed_salesperson_name or "Vendedor", "salesperson",
            config.seed_salesperson_password, config.seed_salesperson_phone or None,
            salesperson_code=config.seed_salesperson_code or None,
        ))


if __name__ == "__main__":
    main()
