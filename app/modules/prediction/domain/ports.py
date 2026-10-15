from datetime import date
from typing import Protocol

from app.core.domain import Ruc
from app.modules.prediction.domain.entities import CustomerFeatures, ModelInfo, MonthlyDemand, RepurchaseProbability


class RepurchaseModel(Protocol):
    def predict(self, features: list[CustomerFeatures]) -> list[RepurchaseProbability]:
        """Una probabilidad por cada fila, en el mismo orden. ModelNotLoadedError si no hay modelo."""
        ...


class FeatureReader(Protocol):
    def read(self, rucs: list[Ruc], as_of: date) -> list[CustomerFeatures]: ...


class ModelInfoRepository(Protocol):
    def get(self) -> ModelInfo | None: ...


class DemandReader(Protocol):
    def monthly_demand(self, product_codes: list[str], since: date) -> list[MonthlyDemand]: ...


class ForecastHistoryReader(Protocol):
    def latest_order_date(self) -> date | None: ...

    def first_month(self, product_code: str) -> date | None: ...

    def monthly_history(self, product_code: str, scenario: str, cutoff: date) -> list[MonthlyDemand]: ...


class ForecastModel(Protocol):
    def predict(self, scenario: str, horizon: int, features: dict[str, str | int | float]) -> float: ...


class ForecastTextGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...
