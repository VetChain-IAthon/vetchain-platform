from datetime import date, datetime
from typing import Protocol


class Clock(Protocol):
    """Puerto del reloj. La implementación del sistema vive en infraestructura."""

    def today(self) -> date: ...

    def now(self) -> datetime: ...


class FixedClock:
    """Reloj fijo para pruebas."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def today(self) -> date:
        return self._moment.date()

    def now(self) -> datetime:
        return self._moment
