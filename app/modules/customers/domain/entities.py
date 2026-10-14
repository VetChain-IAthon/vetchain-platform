from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.core.domain import BusinessRuleError, Money, Ruc
from app.modules.customers.domain.value_objects import ContactOutcome, Level, Probability


@dataclass(frozen=True)
class Customer:
    """Cliente de los CSV de Defontana (solo lectura). `salesperson_code` es el vendedor asignado en la ficha del cliente."""

    ruc: Ruc
    name: str
    phone: str | None = None
    email: str | None = None
    region: str | None = None
    customer_type: str | None = None
    salesperson_code: str | None = None


@dataclass(frozen=True)
class CustomerActivity:
    """Resumen de pedidos de un cliente en una ventana (normalmente 12 meses)."""

    ruc: Ruc
    amount: Money
    order_count: int
    order_dates: tuple[date, ...] = ()

    @property
    def last_order_date(self) -> date | None:
        return max(self.order_dates) if self.order_dates else None


@dataclass(frozen=True)
class CustomerStanding:
    """Cliente con su resumen de 12 meses. `level` es None mientras gerencia no defina los umbrales;
    `last_order_date` es la del historial completo, no solo de los 12 meses."""

    customer: Customer
    activity_12m: CustomerActivity
    last_order_date: date | None
    level: Level | None


@dataclass(frozen=True)
class OrderSummary:
    """Un pedido no es una venta facturada. `amount` es sin IGV (subtotal − descuento)."""

    order_no: str
    order_date: date
    amount: Money
    total_with_tax: Money
    status_code: str | None
    salesperson_code: str


@dataclass(frozen=True)
class ProductPurchase:
    product_code: str
    product_name: str
    category_code: str | None
    times_ordered: int
    total_quantity: Decimal
    amount: Money  # sin IGV, sin líneas bonificadas
    last_order_date: date


@dataclass(frozen=True)
class PeriodOrder:
    """Pedido de un período para la ficha de reunión: solo veterinarios, sin IGV y sin bonificadas.
    `list_amount` es el monto antes del descuento de línea (cantidad × precio unitario)."""

    order_no: str
    order_date: date
    salesperson_code: str
    amount: Money
    list_amount: Money

    @property
    def invoice_discount(self) -> Money:
        return self.list_amount - self.amount


@dataclass(frozen=True)
class PeriodProduct:
    """Lo que el cliente pidió de un producto en el período, sin bonificadas."""

    product_code: str
    product_name: str
    category_code: str | None
    order_count: int
    quantity: Decimal
    amount: Money
    last_order_date: date

    @property
    def average_price(self) -> Money | None:
        return self.amount.divided_by(self.quantity) if self.quantity > 0 else None


@dataclass(frozen=True)
class Alert:
    """Alerta diaria de un cliente que conviene contactar. Una por cliente y día."""

    ruc: Ruc
    alert_date: date
    probability: Probability
    money_at_stake: Money
    reasons: tuple[str, ...]
    usual_product_code: str | None = None
    cross_sell_product_code: str | None = None
    salesperson_code: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.reasons:
            raise BusinessRuleError("Una alerta debe tener al menos un motivo.", "missing_alert_reason")
        if self.money_at_stake.is_negative:
            raise BusinessRuleError("El dinero en juego no puede ser negativo.", "invalid_money_at_stake")


@dataclass(frozen=True)
class Contact:
    """Registro de cada vez que alguien contacta a un cliente. El resultado es obligatorio."""

    ruc: Ruc
    user_id: int
    outcome: ContactOutcome
    contact_date: date
    alert_id: int | None = None
    id: int | None = None


@dataclass(frozen=True)
class AlertFigures:
    """Cifras agregadas para explicar una alerta. Por construcción no lleva nombre ni RUC."""

    days_since_last_order: int
    purchase_frequency_days: Decimal | None
    repurchase_probability: Probability
    average_order_amount: Money
    top_families: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class AlertExplanation:
    text: str
    source: str  # ai | fallback
