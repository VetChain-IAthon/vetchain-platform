"""Núcleo compartido (shared_kernel), parte de dominio: tipos pequeños y estables, solo Python estándar."""
from app.core.domain.clock import Clock, FixedClock
from app.core.domain.data_origin import DataOrigin
from app.core.domain.date_range import DateRange
from app.core.domain.errors import (
    BusinessRuleError,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.domain.money import Money
from app.core.domain.percentage import Percentage
from app.core.domain.ruc import Ruc
from app.core.domain.unit_of_work import UnitOfWork

__all__ = [
    "BusinessRuleError",
    "Clock",
    "ConflictError",
    "DataOrigin",
    "DateRange",
    "DomainError",
    "FixedClock",
    "ForbiddenError",
    "Money",
    "NotFoundError",
    "Percentage",
    "Ruc",
    "UnauthorizedError",
    "UnitOfWork",
]
