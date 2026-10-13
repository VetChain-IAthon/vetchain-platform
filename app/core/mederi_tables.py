"""Tablas importadas de los CSV de Mederi (solo lectura para los módulos).

Los CSV originales NO traen encabezados: los nombres de columnas son propuestos.
Pendiente confirmar con Mederi: kardex.balance = stock mensual; payments.order_id enlaza con orders.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PEN = Numeric(12, 2)


class Customer(Base):
    __tablename__ = "customers"
    ruc: Mapped[str] = mapped_column(String(11), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(200))
    region: Mapped[str | None] = mapped_column(String(80))  # departamento del Perú
    customer_type: Mapped[str | None] = mapped_column(String(20))  # empresa / persona


class SalesRep(Base):
    __tablename__ = "sales_reps"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Product(Base):
    __tablename__ = "products"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(250))
    family: Mapped[str | None] = mapped_column(String(80))


class Order(Base):
    """Un pedido no es una venta facturada: el estado indica en qué punto está."""
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    order_date: Mapped[date]
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    sales_rep_code: Mapped[str | None] = mapped_column(ForeignKey("sales_reps.code"))
    subtotal: Mapped[Decimal] = mapped_column(PEN)
    discount: Mapped[Decimal] = mapped_column(PEN, default=0)
    igv: Mapped[Decimal] = mapped_column(PEN, default=0)
    total: Mapped[Decimal] = mapped_column(PEN)
    status: Mapped[str | None] = mapped_column(String(30))


class OrderItem(Base):
    __tablename__ = "order_items"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    line: Mapped[int] = mapped_column(primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(PEN)
    discount: Mapped[Decimal] = mapped_column(PEN, default=0)
    total: Mapped[Decimal] = mapped_column(PEN)


class Kardex(Base):
    __tablename__ = "kardex"
    warehouse: Mapped[str] = mapped_column(String(10), primary_key=True)
    year: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[int] = mapped_column(primary_key=True)
    product_code: Mapped[str] = mapped_column(ForeignKey("products.code"), primary_key=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # por confirmar: stock mensual


class Payment(Base):
    """Cobro registrado por Mederi."""
    __tablename__ = "payments"
    payment_number: Mapped[str] = mapped_column(String(30), primary_key=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"), index=True)  # por confirmar
    ruc: Mapped[str] = mapped_column(ForeignKey("customers.ruc"), index=True)
    amount: Mapped[Decimal] = mapped_column(PEN)
    payment_date: Mapped[date]
