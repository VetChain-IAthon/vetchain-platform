from datetime import date
from decimal import Decimal
from urllib.parse import quote

from app.core.domain import BusinessRuleError, Money
from app.core.domain.numbers import to_decimal
from app.modules.customers.domain.entities import Alert, CustomerActivity
from app.modules.customers.domain.value_objects import CustomerStatus, Level, LevelThresholds, PurchaseRhythm


class LevelClassifier:
    """Nivel según el monto de pedidos de 12 meses y los umbrales de settings."""

    def __init__(self, thresholds: LevelThresholds) -> None:
        self._thresholds = thresholds

    def classify(self, amount_12m: Money) -> Level:
        if amount_12m >= self._thresholds.min_amount_a:
            return Level.A
        if amount_12m >= self._thresholds.min_amount_b:
            return Level.B
        return Level.C


class DormancyEvaluator:
    """Compara los días sin pedidos con el ritmo habitual del cliente.

    at_risk: pasaron más de `at_risk_factor` veces su ritmo. dormant: más de `dormant_factor` veces.
    Si el cliente no tiene ritmo (menos de dos pedidos) se usa `default_rhythm`.
    Los factores los define el negocio; no hay valores por defecto a propósito.
    """

    def __init__(self, at_risk_factor: Decimal, dormant_factor: Decimal, default_rhythm: PurchaseRhythm) -> None:
        at_risk_factor, dormant_factor = to_decimal(at_risk_factor), to_decimal(dormant_factor)
        if not Decimal(1) <= at_risk_factor < dormant_factor:
            raise BusinessRuleError("Se necesita 1 <= factor de riesgo < factor de dormido.", "invalid_dormancy_factors")
        self._at_risk = at_risk_factor
        self._dormant = dormant_factor
        self._default_rhythm = default_rhythm

    def evaluate(self, last_order_date: date | None, rhythm: PurchaseRhythm | None, today: date) -> CustomerStatus:
        if last_order_date is None:
            return CustomerStatus.DORMANT
        days = (today - last_order_date).days
        average = (rhythm or self._default_rhythm).average_days
        if days > average * self._dormant:
            return CustomerStatus.DORMANT
        if days > average * self._at_risk:
            return CustomerStatus.AT_RISK
        return CustomerStatus.ACTIVE


class AlertPrioritizer:
    """Dinero en juego = monto de pedidos de 12 meses ÷ número de pedidos (lo que vale un pedido típico)."""

    @staticmethod
    def money_at_stake(activity_12m: CustomerActivity) -> Money:
        if activity_12m.order_count == 0:
            return Money.zero()
        return activity_12m.amount.divided_by(activity_12m.order_count)

    @staticmethod
    def prioritize(alerts: "list[Alert]") -> "list[Alert]":
        """Primero más dinero en juego; a igual monto, mayor probabilidad."""
        return sorted(alerts, key=lambda alert: (alert.money_at_stake, alert.probability), reverse=True)


class WhatsappLinkBuilder:
    """Arma el enlace wa.me con el mensaje sugerido. Solo celulares del Perú (9 dígitos que empiezan con 9)."""

    @staticmethod
    def build(phone: str | None, message: str) -> str:
        digits = "".join(ch for ch in (phone or "") if ch.isdigit())
        if len(digits) == 11 and digits.startswith("51"):
            digits = digits[2:]
        if len(digits) != 9 or not digits.startswith("9"):
            raise BusinessRuleError("El cliente no tiene un celular válido para WhatsApp.", "invalid_whatsapp_phone")
        return f"https://wa.me/51{digits}?text={quote(message)}"
