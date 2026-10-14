from app.core.domain import Money
from app.modules.settings.domain.entities import Level, LevelThresholds


class LevelPolicy:
    """Clasifica a un cliente por el monto de sus pedidos en los últimos 12 meses."""

    def __init__(self, thresholds: LevelThresholds) -> None:
        self._thresholds = thresholds

    def classify(self, amount_12m: Money) -> Level:
        if amount_12m >= self._thresholds.min_amount_a:
            return Level.A
        if amount_12m >= self._thresholds.min_amount_b:
            return Level.B
        return Level.C
