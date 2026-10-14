"""Fachada de lectura para otros módulos, con alcance de cartera aplicado en customers."""
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.core.application import SessionUser


@dataclass(frozen=True)
class CommercialTerms:
    level: str
    max_discount_pct: Decimal
    margin_pct: Decimal
    credit_days: int


_get_terms: Callable[[str, SessionUser], CommercialTerms] | None = None
_ensure_access: Callable[[str, SessionUser], None] | None = None


def configure(get_terms: Callable[[str, SessionUser], CommercialTerms],
              ensure_access: Callable[[str, SessionUser], None]) -> None:
    global _get_terms, _ensure_access
    _get_terms = get_terms
    _ensure_access = ensure_access


def get_commercial_terms(ruc: str, user: SessionUser) -> CommercialTerms:
    if _get_terms is None:
        raise RuntimeError("customers no está configurado: falta importar su interfaz.")
    return _get_terms(ruc, user)


def ensure_customer_access(ruc: str, user: SessionUser) -> None:
    if _ensure_access is None:
        raise RuntimeError("customers no está configurado: falta importar su interfaz.")
    _ensure_access(ruc, user)
