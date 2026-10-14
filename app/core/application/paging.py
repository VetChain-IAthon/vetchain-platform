from dataclasses import dataclass
from typing import Generic, TypeVar

from app.core.domain.errors import BusinessRuleError

T = TypeVar("T")

MAX_PER_PAGE = 100


@dataclass(frozen=True)
class Paging:
    page: int = 1
    per_page: int = 20

    def __post_init__(self) -> None:
        if self.page < 1:
            raise BusinessRuleError("La página debe ser 1 o mayor.", "invalid_paging")
        if not 1 <= self.per_page <= MAX_PER_PAGE:
            raise BusinessRuleError(f"per_page debe estar entre 1 y {MAX_PER_PAGE}.", "invalid_paging")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


@dataclass(frozen=True)
class Page(Generic[T]):
    """Forma de todas las listas: items, total, page, per_page."""

    items: tuple[T, ...]
    total: int
    page: int
    per_page: int

    @classmethod
    def of(cls, items: "list[T] | tuple[T, ...]", total: int, paging: Paging) -> "Page[T]":
        return cls(tuple(items), total, paging.page, paging.per_page)
