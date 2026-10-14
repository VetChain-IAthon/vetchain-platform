"""Fachada de reports para otros módulos (hoy, explanations). Solo tipos simples: str, date y listas.

Recibe primitivos y no `InsightQuery` para no importar el dominio de explanations (punto abierto 2 de docs/capas.md).
La interfaz de reports registra al cargarse cómo abrir los repositorios (`configure`).
"""
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date

from app.core.domain import BusinessRuleError, DataOrigin, UnitOfWork
from app.modules.reports.application.use_cases import GetSalesReport, GetSalespeopleReport, ReportQuery
from app.modules.reports.domain.ports import SalesReadRepository

Scope = Callable[[], AbstractContextManager[tuple[SalesReadRepository, UnitOfWork]]]
_scope: Scope | None = None

TOP_ROWS = 10  # filas máximas por respuesta; Gemini solo resume estas filas agregadas


def configure(scope: Scope) -> None:
    global _scope
    _scope = scope


@dataclass(frozen=True)
class AllowedQueryResult:
    rows: list[dict[str, str]]
    sources: list[str]
    data_origin: str


# Tipos que se pueden responder hoy con los reportes que existen. Los demás (estado, nivel o región de clientes,
# antigüedad de deuda) necesitan las alertas, los umbrales o cobros enlazados con pedidos.
SUPPORTED_FILTERS = {
    "sales_by_month": {"salesperson_code"},
    "sales_by_family": {"salesperson_code"},
    "top_products": {"salesperson_code"},
    "salesperson_performance": set(),
}


def _open():
    if _scope is None:
        raise RuntimeError("reports no está configurado: falta importar app.modules.reports.interface.")
    return _scope()


def run_allowed_query(query_type: str, date_from: date | None, date_to: date | None,
                      filters: dict[str, str]) -> AllowedQueryResult:
    """Ejecuta una consulta de la lista cerrada y devuelve filas agregadas (nunca filas por cliente)."""
    allowed = SUPPORTED_FILTERS.get(query_type)
    if allowed is None:
        raise BusinessRuleError("Esa consulta todavía no se puede responder con los datos disponibles.",
                                "query_not_available")
    unknown = set(filters) - allowed
    if unknown:
        raise BusinessRuleError(f"Esa consulta no admite el filtro: {', '.join(sorted(unknown))}.", "filter_not_supported")
    query = ReportQuery(date_from, date_to, filters.get("salesperson_code"))
    with _open() as (sales, uow):
        if query_type == "salesperson_performance":
            report = GetSalespeopleReport(sales, uow).execute(query)
            rows = [{"vendedor": item.name, "monto_pedido": str(item.amount.amount), "pedidos": str(item.order_count),
                     "clientes": str(item.customer_count), "participacion_pct": _text(item.share_pct)}
                    for item in report.items[:TOP_ROWS]]
            return AllowedQueryResult(rows, [_source("/reports/salespeople", report.period)], DataOrigin.REAL.value)
        report = GetSalesReport(sales, uow).execute(query)
    if query_type == "sales_by_month":
        rows = [{"mes": m.month.strftime("%Y-%m"), "monto_pedido": str(m.amount.amount), "pedidos": str(m.order_count)}
                for m in report.monthly]
    elif query_type == "sales_by_family":
        rows = [{"familia": c.code or "sin categoría", "monto_pedido": str(c.amount.amount)}
                for c in report.categories[:TOP_ROWS]]
    else:
        rows = [{"codigo": p.code, "producto": p.name, "monto_pedido": str(p.amount.amount)}
                for p in report.products[:TOP_ROWS]]
    return AllowedQueryResult(rows, [_source("/reports/sales", report.period)], DataOrigin.REAL.value)


def _source(path: str, period) -> str:
    if period.date_range is None:
        return path
    return f"{path}?from={period.date_range.from_date.isoformat()}&to={period.date_range.to_date.isoformat()}"


def _text(value) -> str:
    return "sin dato" if value is None else str(value)
