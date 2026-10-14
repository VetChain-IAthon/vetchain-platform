from dataclasses import dataclass

from app.core.domain.errors import BusinessRuleError

MIN_DIGITS = 8
MAX_DIGITS = 15


@dataclass(frozen=True, order=True)
class Ruc:
    """Documento tributario del cliente: normalmente un RUC de 11 dígitos.

    En los datos de Mederi hay 18 clientes con otro documento (12 de 8 dígitos, que parecen DNI, con pedidos
    hasta 2026), así que se aceptan de 8 a 15 dígitos y `kind` dice de qué tipo es. Ver docs/dudas-mederi.md.
    """

    value: str

    def __post_init__(self) -> None:
        value = str(self.value).strip()
        if not value.isdigit() or not MIN_DIGITS <= len(value) <= MAX_DIGITS:
            raise BusinessRuleError("El RUC o documento debe tener entre 8 y 15 dígitos.", "invalid_ruc")
        object.__setattr__(self, "value", value)

    @property
    def is_standard_ruc(self) -> bool:
        return len(self.value) == 11

    @property
    def kind(self) -> str:
        """company (RUC 20…), person (RUC 10, 15 o 17…) u other."""
        if self.is_standard_ruc and self.value.startswith("20"):
            return "company"
        if self.is_standard_ruc and self.value[:2] in ("10", "15", "17"):
            return "person"
        return "other"

    def __str__(self) -> str:
        return self.value
