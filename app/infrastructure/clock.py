from datetime import date, datetime
from zoneinfo import ZoneInfo

_LIMA = ZoneInfo("America/Lima")


class SystemClock:
    """Implementa el puerto Clock con la hora de Lima (Mederi opera en Perú)."""

    def today(self) -> date:
        return self.now().date()

    def now(self) -> datetime:
        return datetime.now(_LIMA)
