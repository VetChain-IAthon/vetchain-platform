"""Fuentes de datos y columnas propuestas de cada CSV (sin encabezados). Pendiente confirmar con Mederi."""
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.core.domain.numbers import to_decimal


class SourceName(StrEnum):
    CUSTOMERS = "customers"
    SALESPEOPLE = "salespeople"
    PRODUCTS = "products"
    ORDERS = "orders"
    ORDER_LINES = "order_lines"
    STOCK_BALANCES = "stock_balances"
    PAYMENTS = "payments"


class ColumnType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"


_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType = ColumnType.TEXT
    required: bool = True
    max_length: int | None = None

    def parse(self, raw: str) -> Any:
        """Devuelve el valor convertido o lanza ValueError con un mensaje en español."""
        value = raw.strip()
        if not value:
            if self.required:
                raise ValueError(f"'{self.name}' es obligatorio.")
            return None
        if self.type is ColumnType.TEXT:
            if self.max_length is not None and len(value) > self.max_length:
                raise ValueError(f"'{self.name}' supera {self.max_length} caracteres.")
            return value
        if self.type is ColumnType.INTEGER:
            if not value.lstrip("-").isdigit():
                raise ValueError(f"'{self.name}' debe ser un número entero.")
            return int(value)
        if self.type is ColumnType.DECIMAL:
            try:
                return to_decimal(value)
            except ValueError:
                raise ValueError(f"'{self.name}' debe ser un número (use punto decimal).") from None
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        raise ValueError(f"'{self.name}' debe ser una fecha AAAA-MM-DD o DD/MM/AAAA.")


@dataclass(frozen=True)
class CsvSchema:
    columns: tuple[Column, ...]

    @property
    def width(self) -> int:
        return len(self.columns)


@dataclass(frozen=True)
class DataSource:
    name: SourceName
    description: str
    schema: CsvSchema


def _schema(*columns: Column) -> CsvSchema:
    return CsvSchema(columns)


_T, _I, _D, _F = ColumnType.TEXT, ColumnType.INTEGER, ColumnType.DECIMAL, ColumnType.DATE

SOURCES: dict[SourceName, DataSource] = {
    source.name: source
    for source in (
        DataSource(SourceName.CUSTOMERS, "Clientes", _schema(
            Column("ruc", _T, max_length=11), Column("name", _T, max_length=200),
            Column("address", _T, False, 300), Column("phone", _T, False, 40), Column("email", _T, False, 200),
            Column("region", _T, False, 80), Column("customer_type", _T, False, 20),
        )),
        DataSource(SourceName.SALESPEOPLE, "Vendedores", _schema(
            Column("code", _T, max_length=20), Column("name", _T, max_length=120),
        )),
        DataSource(SourceName.PRODUCTS, "Productos", _schema(
            Column("code", _T, max_length=30), Column("name", _T, max_length=250), Column("family", _T, False, 80),
        )),
        DataSource(SourceName.ORDERS, "Pedidos (no son ventas facturadas)", _schema(
            Column("id", _T, max_length=30), Column("order_date", _F), Column("ruc", _T, max_length=11),
            Column("salesperson_code", _T, False, 20), Column("subtotal", _D), Column("discount", _D, False),
            Column("igv", _D, False), Column("total", _D), Column("status", _T, False, 30),
        )),
        DataSource(SourceName.ORDER_LINES, "Detalle de pedidos", _schema(
            Column("order_id", _T, max_length=30), Column("line", _I), Column("product_code", _T, max_length=30),
            Column("quantity", _D), Column("unit_price", _D), Column("discount", _D, False), Column("total", _D),
        )),
        DataSource(SourceName.STOCK_BALANCES, "Kardex (saldo mensual por almacén)", _schema(
            Column("warehouse", _T, max_length=10), Column("year", _I), Column("month", _I),
            Column("product_code", _T, max_length=30), Column("balance", _D),
        )),
        DataSource(SourceName.PAYMENTS, "Cobros", _schema(
            Column("payment_number", _T, max_length=30), Column("order_id", _T, False, 30),
            Column("ruc", _T, max_length=11), Column("amount", _D), Column("payment_date", _F),
        )),
    )
}

# Fila validada: nombre de columna → valor convertido.
Record = dict[str, Any]
