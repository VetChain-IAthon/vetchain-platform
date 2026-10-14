from decimal import Decimal, InvalidOperation


def to_decimal(value: Decimal | int | str) -> Decimal:
    """Convierte a Decimal. Rechaza float para no arrastrar errores de redondeo."""
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("Usa Decimal, int o str; no float.")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError(f"No es un número válido: {value!r}") from None
    if not result.is_finite():
        raise ValueError(f"No es un número válido: {value!r}")
    return result
