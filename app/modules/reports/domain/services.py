from datetime import date, timedelta
from decimal import Decimal

from app.core.domain import BusinessRuleError, Money
from app.core.domain.numbers import to_decimal
from app.modules.reports.domain.entities import AgingBucket, KpiStatus, Receivable

_BUCKETS = (("Por vencer", 0, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("Más de 90", 91, None))


class KpiEvaluator:
    """ok si alcanza la meta; warn si está dentro de la tolerancia; critical si no."""

    def __init__(self, tolerance_pct: Decimal) -> None:
        tolerance_pct = to_decimal(tolerance_pct)
        if not Decimal(0) <= tolerance_pct <= Decimal(100):
            raise BusinessRuleError("La tolerancia debe estar entre 0 y 100.", "invalid_tolerance")
        self._tolerance = tolerance_pct / 100

    def evaluate(self, value: Decimal, target: Decimal, higher_is_better: bool = True) -> KpiStatus:
        value, target = to_decimal(value), to_decimal(target)
        if higher_is_better:
            if value >= target:
                return KpiStatus.OK
            return KpiStatus.WARN if value >= target * (1 - self._tolerance) else KpiStatus.CRITICAL
        if value <= target:
            return KpiStatus.OK
        return KpiStatus.WARN if value <= target * (1 + self._tolerance) else KpiStatus.CRITICAL


class AgingCalculator:
    """Vencimiento estimado = fecha del pedido + días de crédito del nivel. Resultado marcado como estimated."""

    def __init__(self, credit_days_by_level: dict[str, int]) -> None:
        self._credit_days = credit_days_by_level

    def days_overdue(self, receivable: Receivable, today: date) -> int:
        if receivable.level not in self._credit_days:
            raise BusinessRuleError(f"No hay días de crédito para el nivel {receivable.level}.", "unknown_level")
        due = receivable.order_date + timedelta(days=self._credit_days[receivable.level])
        return max((today - due).days, 0)

    def buckets(self, receivables: "list[Receivable]", today: date) -> list[AgingBucket]:
        totals = {label: Money.zero() for label, _, _ in _BUCKETS}
        for receivable in receivables:
            days = self.days_overdue(receivable, today)
            label = next(label for label, low, high in _BUCKETS if days >= low and (high is None or days <= high))
            totals[label] = totals[label] + receivable.outstanding
        return [AgingBucket(label, low, high, totals[label]) for label, low, high in _BUCKETS]


class RecoveredAmountCalculator:
    """Monto recuperado = pedidos de clientes contactados hechos dentro de `window_days` después del contacto.

    Definición propuesta, a validar con gerencia.
    """

    def __init__(self, window_days: int) -> None:
        if window_days < 1:
            raise BusinessRuleError("La ventana debe ser de al menos 1 día.", "invalid_window")
        self._window = timedelta(days=window_days)

    def recovered(self, contact_dates: dict[str, date], orders: "list[tuple[str, date, Money]]") -> Money:
        """`contact_dates`: primer contacto por RUC. `orders`: (ruc, fecha, monto)."""
        total = Money.zero()
        for ruc, order_date, amount in orders:
            contacted_on = contact_dates.get(ruc)
            if contacted_on is not None and contacted_on <= order_date <= contacted_on + self._window:
                total = total + amount
        return total
