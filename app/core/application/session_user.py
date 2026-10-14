from dataclasses import dataclass

MANAGER = "manager"
SALESPERSON = "salesperson"


@dataclass(frozen=True)
class SessionUser:
    """Usuario de la sesión tal como lo ven todos los módulos: tipos simples, sin depender de auth."""

    id: int
    role: str  # manager | salesperson
    salesperson_code: str | None

    @property
    def is_manager(self) -> bool:
        return self.role == MANAGER
