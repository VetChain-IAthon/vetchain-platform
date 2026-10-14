"""ORM de las 7 tablas de Defontana (el ERP de Mederi). Solo las escribe la carga de CSV; los módulos solo las leen.

Decisiones que no hay que deshacer:
- Los códigos se guardan como texto con ceros a la izquierda ('001').
- receipts no se enlaza con orders: el CSV trae el número de comprobante, no el de pedido.
- stock_balances no tiene FK a products: 5 códigos del kardex no están en el catálogo.
- order_lines.dup_seq conserva los 18 pares (pedido, línea) repetidos.
- Importes Numeric(14,2), cantidades Numeric(14,4), precio unitario Numeric(18,10).

Las columnas marcadas POR CONFIRMAR están listadas en docs/dudas-mederi.md.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

AMOUNT = Numeric(14, 2)
QUANTITY = Numeric(14, 4)
UNIT_PRICE = Numeric(18, 10)
CODE = String(3)


class Salesperson(Base):
    __tablename__ = "salespeople"

    code: Mapped[str] = mapped_column(CODE, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean)


class Customer(Base):
    __tablename__ = "customers"

    ruc: Mapped[str] = mapped_column(String(15), primary_key=True)  # 18 clientes no tienen 11 dígitos (ver dudas)
    name: Mapped[str] = mapped_column(String(150))
    address: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(120))
    salesperson_code: Mapped[str] = mapped_column(ForeignKey("salespeople.code"), index=True)
    department_code: Mapped[str | None] = mapped_column(CODE)
    department: Mapped[str | None] = mapped_column(String(60))
    segment_code: Mapped[str | None] = mapped_column(CODE)  # POR CONFIRMAR
    condition_code: Mapped[str | None] = mapped_column(CODE)  # POR CONFIRMAR: condición de pago
    is_active: Mapped[bool] = mapped_column(Boolean)
    tax_id_kind: Mapped[str] = mapped_column(String(10))  # derivada: company | person | other


class Product(Base):
    __tablename__ = "products"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    alias: Mapped[str | None] = mapped_column(String(60))
    category_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    unit_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    is_active: Mapped[bool] = mapped_column(Boolean)
    prefix: Mapped[str] = mapped_column(String(3))  # derivada: primeros 3 caracteres del código
    is_core_product: Mapped[bool] = mapped_column(Boolean, index=True)  # derivada: prefix == 'MED'


class Order(Base):
    """Un pedido no es una venta facturada."""

    __tablename__ = "orders"

    order_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    order_date: Mapped[date] = mapped_column(Date, index=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    salesperson_code: Mapped[str] = mapped_column(ForeignKey("salespeople.code"), index=True)
    channel_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    subtotal: Mapped[Decimal] = mapped_column(AMOUNT)
    discount: Mapped[Decimal] = mapped_column(AMOUNT)
    tax: Mapped[Decimal] = mapped_column(AMOUNT)
    total: Mapped[Decimal] = mapped_column(AMOUNT)
    # T = En tránsito, A = Almacén / Aprobado, C = Cancelado, D = Devuelto / Entregado, NULL = sin dato
    status_code: Mapped[str | None] = mapped_column(String(1))
    is_dispatched: Mapped[bool] = mapped_column(Boolean)  # derivada: status_code == 'T'


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (UniqueConstraint("order_no", "line_no", "dup_seq", name="uq_order_lines_order_line_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(ForeignKey("orders.order_no"), index=True)
    line_no: Mapped[int] = mapped_column(Integer)
    dup_seq: Mapped[int] = mapped_column(Integer, default=0)  # 0 normal; 1 para la segunda línea repetida
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"), index=True)
    unit_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    quantity_dispatched: Mapped[Decimal] = mapped_column(QUANTITY)  # POR CONFIRMAR
    unit_price: Mapped[Decimal] = mapped_column(UNIT_PRICE)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    line_total: Mapped[Decimal] = mapped_column(AMOUNT)  # = quantity × unit_price × (1 − discount_pct/100), sin IGV
    is_bonus: Mapped[bool] = mapped_column(Boolean)  # derivada: unit_price <= 0.01 (precio simbólico)


class StockBalance(Base):
    __tablename__ = "stock_balances"

    warehouse_code: Mapped[str] = mapped_column(CODE, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_code: Mapped[str] = mapped_column(String(20), primary_key=True)  # sin FK a products, a propósito
    product_name: Mapped[str | None] = mapped_column(String(150))
    balance: Mapped[Decimal] = mapped_column(QUANTITY)  # POR CONFIRMAR: saldo al cierre del mes
    period_end: Mapped[date] = mapped_column(Date, index=True)  # derivada: último día del mes


class Receipt(Base):
    """Cobro. No se enlaza con orders: trae número de comprobante, no de pedido."""

    __tablename__ = "receipts"

    receipt_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    document_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    receipt_date: Mapped[date] = mapped_column(Date, index=True)
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    type_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    code_c6: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    payment_method_code: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    code_c8: Mapped[str] = mapped_column(CODE)  # POR CONFIRMAR
    reference_no: Mapped[str | None] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(AMOUNT)
    applied_date: Mapped[date] = mapped_column(Date)  # POR CONFIRMAR


SOURCE_MODELS = (Salesperson, Customer, Product, Order, OrderLine, StockBalance, Receipt)
