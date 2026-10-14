"""Las 7 fuentes de Defontana y su mapa CSV → columna (sin encabezados; `index` es la posición desde 0).

Debe coincidir con app/infrastructure/loaders/defontana_csv.py (lo verifica tests/test_module_repositories.py).
Las columnas que no aparecen no se guardan: están vacías, son constantes o repiten datos de otra tabla.
"""
from dataclasses import dataclass
from datetime import date
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
    RECEIPTS = "receipts"


class ColumnType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass(frozen=True)
class Column:
    index: int
    name: str
    type: ColumnType = ColumnType.TEXT
    required: bool = True

    def parse(self, raw: str) -> Any:
        """Devuelve el valor convertido (None si es opcional y está vacío) o lanza ValueError en español."""
        value = raw.strip()
        if not value:
            if self.required:
                raise ValueError(f"falta {self.name}")
            return None
        try:
            if self.type is ColumnType.INTEGER:
                return int(value)
            if self.type is ColumnType.DECIMAL:
                return to_decimal(value)
            if self.type is ColumnType.DATE:
                return date.fromisoformat(value)
            if self.type is ColumnType.BOOLEAN:
                if value not in ("0", "1"):
                    raise ValueError(value)
                return value == "1"
        except ValueError:
            raise ValueError(f"{self.name} inválido") from None
        return value


@dataclass(frozen=True)
class CsvSchema:
    width: int  # columnas que trae el CSV
    columns: tuple[Column, ...]  # columnas que se guardan


@dataclass(frozen=True)
class DataSource:
    name: SourceName
    number: int  # mederi-1-ventas.csv … mederi-7-vendedores.csv
    description: str
    schema: CsvSchema


_T, _I, _D, _F, _B = ColumnType.TEXT, ColumnType.INTEGER, ColumnType.DECIMAL, ColumnType.DATE, ColumnType.BOOLEAN


def _source(name, number, description, width, *columns) -> DataSource:
    return DataSource(name, number, description, CsvSchema(width, tuple(columns)))


SOURCES: dict[SourceName, DataSource] = {
    source.name: source
    for source in (
        _source(SourceName.SALESPEOPLE, 7, "Vendedores", 5,
                Column(0, "code"), Column(1, "name"), Column(2, "location", required=False), Column(4, "is_active", _B)),
        _source(SourceName.CUSTOMERS, 1, "Clientes", 16,
                Column(0, "ruc"), Column(1, "name"), Column(2, "address", required=False),
                Column(3, "phone", required=False), Column(4, "email", required=False), Column(5, "salesperson_code"),
                Column(7, "department_code", required=False), Column(8, "department", required=False),
                Column(9, "segment_code", required=False), Column(11, "condition_code", required=False),
                Column(14, "is_active", _B)),
        _source(SourceName.PRODUCTS, 4, "Productos", 14,
                Column(0, "code"), Column(1, "name"), Column(2, "alias", required=False), Column(3, "category_code"),
                Column(5, "unit_code"), Column(10, "is_active", _B)),
        _source(SourceName.ORDERS, 2, "Pedidos (no son ventas facturadas)", 12,
                Column(0, "order_no"), Column(1, "order_date", _F), Column(2, "ruc"), Column(4, "salesperson_code"),
                Column(6, "channel_code"), Column(7, "subtotal", _D), Column(8, "discount", _D), Column(9, "tax", _D),
                Column(10, "total", _D), Column(11, "status_code", required=False)),
        _source(SourceName.ORDER_LINES, 3, "Detalle de pedidos", 14,
                Column(0, "order_no"), Column(4, "line_no", _I), Column(5, "product_code"), Column(7, "unit_code"),
                Column(8, "quantity", _D), Column(9, "quantity_dispatched", _D), Column(11, "unit_price", _D),
                Column(12, "discount_pct", _D), Column(13, "line_total", _D)),
        _source(SourceName.STOCK_BALANCES, 5, "Kardex (saldo mensual por almacén)", 6,
                Column(0, "warehouse_code"), Column(1, "year", _I), Column(2, "month", _I), Column(3, "product_code"),
                Column(4, "product_name", required=False), Column(5, "balance", _D)),
        _source(SourceName.RECEIPTS, 6, "Cobros (sin enlace a pedidos)", 12,
                Column(0, "receipt_no"), Column(1, "receipt_date", _F), Column(2, "ruc"), Column(4, "type_code"),
                Column(5, "document_no"), Column(6, "code_c6"), Column(7, "payment_method_code"), Column(8, "code_c8"),
                Column(9, "reference_no", required=False), Column(10, "amount", _D), Column(11, "applied_date", _F)),
    )
}

# Fila validada: nombre de columna → valor convertido.
Record = dict[str, Any]
