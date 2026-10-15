"""Adaptadores de solo lectura para el pronóstico de demanda registrada."""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.source_models import Order, OrderLine
from app.modules.prediction.domain.entities import MonthlyDemand


class SqlForecastHistoryReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_order_date(self) -> date | None:
        return self.session.scalar(
            select(func.max(Order.order_date)).join(OrderLine, OrderLine.order_no == Order.order_no)
            .where(Order.status_code.in_(("T", "A")), OrderLine.quantity > 0)
        )

    def first_month(self, product_code: str) -> date | None:
        first = self.session.scalar(
            select(func.min(Order.order_date)).join(OrderLine, OrderLine.order_no == Order.order_no)
            .where(OrderLine.product_code == product_code, Order.status_code.in_(("T", "A")), OrderLine.quantity > 0)
        )
        return first.replace(day=1) if first else None

    def monthly_history(self, product_code: str, scenario: str, cutoff: date) -> list[MonthlyDemand]:
        year = func.extract("year", Order.order_date)
        month = func.extract("month", Order.order_date)
        next_month = date(cutoff.year + (cutoff.month == 12), cutoff.month % 12 + 1, 1)
        query = (
            select(year.label("year"), month.label("month"), func.sum(OrderLine.quantity).label("quantity"))
            .select_from(OrderLine).join(Order, Order.order_no == OrderLine.order_no)
            .where(OrderLine.product_code == product_code, Order.order_date < next_month,
                   Order.status_code.in_(("T", "A")), OrderLine.quantity > 0)
            .group_by(year, month).order_by(year, month)
        )
        if scenario == "B":
            query = query.where(OrderLine.unit_price > 0)
        return [MonthlyDemand(product_code, date(int(row.year), int(row.month), 1), row.quantity)
                for row in self.session.execute(query)]


@lru_cache(maxsize=4)
def _load_model(directory: str, scenario: str, horizon: int):
    root = Path(directory)
    stem = f"extratrees_{scenario}_{horizon}m"
    metadata_path, model_path = root / f"{stem}.json", root / f"{stem}.joblib"
    if not metadata_path.is_file() or not model_path.is_file():
        raise FileNotFoundError("Falta el modelo privado Extra Trees o su metadata.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("escenario") != scenario or metadata.get("horizonte_meses") != horizon:
        raise ValueError("La metadata del modelo no coincide con el escenario y horizonte.")
    if metadata.get("sklearn") != sklearn.__version__:
        raise ValueError("La versión de scikit-learn no coincide con la del entrenamiento.")
    model = joblib.load(model_path)  # solo artefactos privados de origen confiable
    features = metadata.get("features")
    if not isinstance(features, list) or list(getattr(model, "feature_names_in_", [])) != features:
        raise ValueError("Las variables del modelo no coinciden con su metadata.")
    return model, features


class PrivateExtraTreesModel:
    def __init__(self, directory: str) -> None:
        self.directory = directory

    def predict(self, scenario: str, horizon: int, features: dict[str, str | int | float]) -> float:
        if not self.directory:
            raise FileNotFoundError("Configura FORECAST_MODELS_DIR para usar Extra Trees.")
        model, names = _load_model(self.directory, scenario, horizon)
        return float(model.predict(pd.DataFrame([{name: features[name] for name in names}]))[0])
