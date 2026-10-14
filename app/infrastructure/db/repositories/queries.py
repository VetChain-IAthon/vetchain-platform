"""Consultas de lectura sobre las tablas de Defontana. Devuelven dicts simples, nunca entidades ORM.

Reglas incorporadas:
- Un pedido no es una venta facturada: se habla de "pedidos" y "monto pedido".
- Montos sin IGV: salen de order_lines.line_total.
- Solo productos veterinarios (is_core_product) en las métricas.
- Los estados en `exclude_statuses` no cuentan como compra. Por defecto se excluyen solo los cancelados (C),
  igual que SalesDefinition en el dominio de reports.
- El precio de referencia usa solo líneas no bonificadas y es estimado: no es un costo.
Funcionan en PostgreSQL y en SQLite.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from collections.abc import Collection
from typing import Any

from sqlalchemy import and_, case, desc, func, or_, select, true
from sqlalchemy.orm import Session

from app.infrastructure.db.source_models import Order, OrderLine, Product, Receipt, StockBalance

Row = dict[str, Any]

_CENT = Decimal("0.01")
DEFAULT_EXCLUDED = ("C",)


def _counted(exclude_statuses: Collection[str]):
    """Pedidos cuyo estado cuenta como compra. Un estado vacío (NULL) siempre cuenta."""
    if not exclude_statuses:
        return true()
    return or_(Order.status_code.is_(None), Order.status_code.not_in(list(exclude_statuses)))


def _month(session: Session, column):
    if session.get_bind().dialect.name == "sqlite":
        return func.strftime("%Y-%m", column)
    return func.to_char(column, "YYYY-MM")


def _date_filters(column, date_from: date | None, date_to: date | None) -> list:
    filters = []
    if date_from is not None:
        filters.append(column >= date_from)
    if date_to is not None:
        filters.append(column <= date_to)
    return filters


def _core_lines():
    """Pedidos unidos a sus líneas de productos veterinarios."""
    return (
        select()
        .select_from(Order)
        .join(OrderLine, OrderLine.order_no == Order.order_no)
        .join(Product, Product.code == OrderLine.product_code)
        .where(Product.is_core_product.is_(True))
    )


def last_order_per_customer(session: Session, as_of: date | None = None, exclude_statuses: Collection[str] = DEFAULT_EXCLUDED) -> list[Row]:
    """Última compra, cantidad de pedidos y monto (sin IGV, solo veterinarios) por cliente. Base de las alertas."""
    query = _core_lines().add_columns(
        Order.ruc,
        func.max(Order.order_date).label("last_order_date"),
        func.count(func.distinct(Order.order_no)).label("order_count"),
        func.sum(OrderLine.line_total).label("amount"),
    )
    if as_of is not None:
        query = query.where(Order.order_date <= as_of)
    query = query.where(_counted(exclude_statuses))
    query = query.group_by(Order.ruc).order_by(Order.ruc)
    return [dict(row._mapping) for row in session.execute(query)]


def customer_orders(
    session: Session,
    ruc: str,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Row], int]:
    """Pedidos de un cliente, del más reciente al más antiguo. Devuelve (página, total)."""
    filters = [Order.ruc == ruc, *_date_filters(Order.order_date, date_from, date_to)]
    total = session.scalar(select(func.count()).select_from(Order).where(*filters))
    query = (
        select(
            Order.order_no, Order.order_date, Order.salesperson_code, Order.subtotal, Order.discount,
            Order.tax, Order.total, Order.status_code, Order.is_dispatched,
        )
        .where(*filters)
        .order_by(Order.order_date.desc(), Order.order_no.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    return [dict(row._mapping) for row in session.execute(query)], total


def customer_products(session: Session, ruc: str, exclude_statuses: Collection[str] = DEFAULT_EXCLUDED) -> list[Row]:
    """Productos veterinarios que compra un cliente. El monto excluye las líneas bonificadas."""
    query = _core_lines().add_columns(
        Product.code.label("product_code"),
        Product.name.label("product_name"),
        Product.category_code,
        func.count(func.distinct(Order.order_no)).label("order_count"),
        func.sum(OrderLine.quantity).label("quantity"),
        func.sum(case((OrderLine.is_bonus.is_(False), OrderLine.line_total), else_=0)).label("amount"),
        func.max(Order.order_date).label("last_order_date"),
    ).where(Order.ruc == ruc)
    query = query.where(_counted(exclude_statuses))
    query = query.group_by(Product.code, Product.name, Product.category_code).order_by(desc("amount"), Product.code)
    return [dict(row._mapping) for row in session.execute(query)]


def last_paid_price(session: Session, product_code: str) -> Row | None:
    """Último precio pagado por unidad (precio × (1 − descuento %)), sin IGV. Estimado: no es un costo."""
    query = (
        select(OrderLine.unit_price, OrderLine.discount_pct, Order.order_no, Order.order_date)
        .join(Order, Order.order_no == OrderLine.order_no)
        .where(OrderLine.product_code == product_code, OrderLine.is_bonus.is_(False), _counted(DEFAULT_EXCLUDED))
        .order_by(Order.order_date.desc(), Order.order_no.desc(), OrderLine.id.desc())
        .limit(1)
    )
    row = session.execute(query).first()
    if row is None:
        return None
    price = (row.unit_price * (1 - row.discount_pct / 100)).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {
        "product_code": product_code,
        "unit_price": price,
        "order_no": row.order_no,
        "order_date": row.order_date,
        "data_origin": "estimated",
    }


def monthly_sales(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> list[Row]:
    """Pedidos por mes (solo veterinarios, sin IGV): cantidad de pedidos, monto y monto despachado (estado T)."""
    month = _month(session, Order.order_date).label("month")
    query = _core_lines().add_columns(
        month,
        func.count(func.distinct(Order.order_no)).label("order_count"),
        func.sum(OrderLine.line_total).label("amount"),
        func.sum(case((Order.is_dispatched.is_(True), OrderLine.line_total), else_=0)).label("dispatched_amount"),
    ).where(*_date_filters(Order.order_date, date_from, date_to), OrderLine.is_bonus.is_(False))
    query = query.where(_counted(exclude_statuses))
    query = query.group_by(month).order_by(month)
    return [dict(row._mapping) for row in session.execute(query)]


def stock_at(session: Session, year: int, month: int) -> list[Row]:
    """Stock al cierre de un mes sumando almacenes. El kardex solo tiene fila los meses con datos:
    se toma el último saldo de cada (almacén, producto) hasta ese mes."""
    period_end = func.max(StockBalance.period_end)
    end = date(year + month // 12, month % 12 + 1, 1)  # primer día del mes siguiente
    latest = (
        select(StockBalance.warehouse_code, StockBalance.product_code, period_end.label("period_end"))
        .where(StockBalance.period_end < end)
        .group_by(StockBalance.warehouse_code, StockBalance.product_code)
        .subquery()
    )
    query = (
        select(
            StockBalance.product_code,
            func.max(StockBalance.product_name).label("product_name"),
            func.sum(StockBalance.balance).label("balance"),
            func.max(StockBalance.period_end).label("last_period_end"),
        )
        .join(
            latest,
            and_(
                latest.c.warehouse_code == StockBalance.warehouse_code,
                latest.c.product_code == StockBalance.product_code,
                latest.c.period_end == StockBalance.period_end,
            ),
        )
        .group_by(StockBalance.product_code)
        .order_by(StockBalance.product_code)
    )
    return [dict(row._mapping) for row in session.execute(query)]


def receipts_by_customer(
    session: Session, ruc: str, date_from: date | None = None, date_to: date | None = None
) -> list[Row]:
    """Cobros de un cliente, del más reciente al más antiguo."""
    query = (
        select(
            Receipt.receipt_no, Receipt.document_no, Receipt.receipt_date, Receipt.type_code,
            Receipt.payment_method_code, Receipt.amount, Receipt.applied_date,
        )
        .where(Receipt.ruc == ruc, *_date_filters(Receipt.receipt_date, date_from, date_to))
        .order_by(Receipt.receipt_date.desc(), Receipt.receipt_no.desc(), Receipt.document_no.desc())
    )
    return [dict(row._mapping) for row in session.execute(query)]


def customer_activity(
    session: Session,
    rucs: Collection[str],
    since: date,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> dict[str, Row]:
    """Por cliente, desde `since`: monto (sin IGV, solo veterinarios), cantidad de pedidos y fechas con pedido."""
    query = (
        _core_lines()
        .add_columns(
            Order.ruc,
            Order.order_no,
            Order.order_date,
            func.sum(OrderLine.line_total).label("amount"),
        )
        .where(Order.ruc.in_(list(rucs)), Order.order_date >= since, _counted(exclude_statuses))
        .group_by(Order.ruc, Order.order_no, Order.order_date)
    )
    activity: dict[str, Row] = {}
    for row in session.execute(query):
        item = activity.setdefault(row.ruc, {"amount": Decimal(0), "order_count": 0, "order_dates": []})
        item["amount"] += row.amount
        item["order_count"] += 1
        item["order_dates"].append(row.order_date)
    for item in activity.values():
        item["order_dates"].sort()
    return activity


def sales_by_category(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> list[Row]:
    """Monto pedido (sin IGV, solo veterinarios) por categoría de producto (category_code, POR CONFIRMAR)."""
    query = (
        _core_lines()
        .add_columns(Product.category_code, func.sum(OrderLine.line_total).label("amount"))
        .where(*_date_filters(Order.order_date, date_from, date_to), _counted(exclude_statuses),
               OrderLine.is_bonus.is_(False))
        .group_by(Product.category_code)
        .order_by(desc("amount"), Product.category_code)
    )
    return [dict(row._mapping) for row in session.execute(query)]


def amounts_by_customer(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> list[Row]:
    """Monto pedido (sin IGV, solo veterinarios) y cantidad de pedidos por cliente, de mayor a menor monto."""
    query = (
        _core_lines()
        .add_columns(Order.ruc, func.sum(OrderLine.line_total).label("amount"),
                     func.count(func.distinct(Order.order_no)).label("order_count"))
        .where(*_date_filters(Order.order_date, date_from, date_to), _counted(exclude_statuses),
               OrderLine.is_bonus.is_(False))
        .group_by(Order.ruc)
        .order_by(desc("amount"), Order.ruc)
    )
    return [dict(row._mapping) for row in session.execute(query)]


def products_missing_from_catalog(session: Session) -> list[str]:
    """Control de calidad: códigos del kardex que no están en products."""
    query = (
        select(StockBalance.product_code)
        .distinct()
        .where(~StockBalance.product_code.in_(select(Product.code)))
        .order_by(StockBalance.product_code)
    )
    return list(session.scalars(query))


def customer_period_orders(
    session: Session,
    ruc: str,
    date_from: date,
    date_to: date,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> list[Row]:
    """Pedidos de un cliente en el período (solo veterinarios, sin IGV, sin bonificadas), del más antiguo al más reciente.
    `list_amount` es cantidad × precio unitario antes del descuento de línea: la diferencia es el descuento en factura."""
    query = (
        _core_lines()
        .add_columns(
            Order.order_no, Order.order_date, Order.salesperson_code,
            func.sum(OrderLine.line_total).label("amount"),
            func.sum(OrderLine.quantity * OrderLine.unit_price).label("list_amount"),
        )
        .where(Order.ruc == ruc, *_date_filters(Order.order_date, date_from, date_to), _counted(exclude_statuses),
               OrderLine.is_bonus.is_(False))
        .group_by(Order.order_no, Order.order_date, Order.salesperson_code)
        .order_by(Order.order_date, Order.order_no)
    )
    return [dict(row._mapping) for row in session.execute(query)]


def customer_period_products(
    session: Session,
    ruc: str,
    date_from: date,
    date_to: date,
    exclude_statuses: Collection[str] = DEFAULT_EXCLUDED,
) -> list[Row]:
    """Productos veterinarios de un cliente en el período, sin líneas bonificadas, de mayor a menor monto."""
    query = (
        _core_lines()
        .add_columns(
            Product.code.label("product_code"), Product.name.label("product_name"), Product.category_code,
            func.count(func.distinct(Order.order_no)).label("order_count"),
            func.sum(OrderLine.quantity).label("quantity"),
            func.sum(OrderLine.line_total).label("amount"),
            func.max(Order.order_date).label("last_order_date"),
        )
        .where(Order.ruc == ruc, *_date_filters(Order.order_date, date_from, date_to), _counted(exclude_statuses),
               OrderLine.is_bonus.is_(False))
        .group_by(Product.code, Product.name, Product.category_code)
        .order_by(desc("amount"), Product.code)
    )
    return [dict(row._mapping) for row in session.execute(query)]


def last_paid_prices(session: Session, product_codes: Collection[str], as_of: date | None = None) -> dict[str, Decimal]:
    """Último precio pagado por unidad (total de línea ÷ cantidad, sin IGV) de cada producto, a cualquier cliente.
    Es el mismo precio de referencia de las cotizaciones: estimado, no es un costo ni un precio de lista oficial."""
    if not product_codes:
        return {}
    query = (
        select(OrderLine.product_code, OrderLine.line_total, OrderLine.quantity)
        .join(Order, Order.order_no == OrderLine.order_no)
        .where(OrderLine.product_code.in_(list(product_codes)), OrderLine.is_bonus.is_(False), OrderLine.quantity > 0,
               _counted(DEFAULT_EXCLUDED), *_date_filters(Order.order_date, None, as_of))
        .order_by(Order.order_date.desc(), Order.order_no.desc(), OrderLine.id.desc())
    )
    prices: dict[str, Decimal] = {}
    for row in session.execute(query):
        if row.product_code not in prices:
            prices[row.product_code] = (row.line_total / row.quantity).quantize(_CENT, rounding=ROUND_HALF_UP)
    return prices
