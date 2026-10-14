from dataclasses import dataclass

from app.core.domain.errors import BusinessRuleError


@dataclass(frozen=True, order=True)
class Ruc:
    """RUC peruano: 11 dígitos."""

    value: str

    def __post_init__(self) -> None:
        value = str(self.value).strip()
        if len(value) != 11 or not value.isdigit():
            raise BusinessRuleError("El RUC debe tener 11 dígitos.", "invalid_ruc")
        object.__setattr__(self, "value", value)

    def __str__(self) -> str:
        return self.value
