"""Integración opcional contra PostgreSQL real.

Se salta si no hay POSTGRES_TEST_URL. Para no tocar datos reales, el nombre de la base debe contener "test":
    createdb vetchain_test
    POSTGRES_TEST_URL=postgresql://usuario:clave@localhost:5432/vetchain_test pytest tests/test_postgres_integration.py
"""
import os
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.database import Base
from app.infrastructure.db.repositories import queries
from app.infrastructure.db.source_models import SOURCE_MODELS, OrderLine
from tests.defontana_sample import load_sample

URL = os.environ.get("POSTGRES_TEST_URL", "")

pytestmark = pytest.mark.skipif(not URL.startswith("postgres"), reason="Sin POSTGRES_TEST_URL")


@pytest.fixture()
def pg_session():
    url = make_url(URL).set(drivername="postgresql+psycopg")
    if "test" not in (url.database or ""):
        pytest.fail("Por seguridad, la base de POSTGRES_TEST_URL debe tener 'test' en el nombre.")
    engine = create_engine(url)
    tables = [model.__table__ for model in SOURCE_MODELS]
    Base.metadata.drop_all(engine, tables=tables)
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine, tables=tables)
    engine.dispose()


def test_load_upsert_and_queries_on_postgres(pg_session):
    load_sample(pg_session)
    load_sample(pg_session)  # upsert: no duplica
    assert pg_session.scalar(select(func.count()).select_from(OrderLine)) == 7
    months = queries.monthly_sales(pg_session)
    assert [(row["month"], row["amount"]) for row in months] == [
        ("2025-01", Decimal("100.01")), ("2025-02", Decimal("45.00")), ("2025-03", Decimal("10.00")),
    ]
    assert queries.last_paid_price(pg_session, "MED0000001")["unit_price"] == Decimal("45.00")
    stock = {row["product_code"]: row["balance"] for row in queries.stock_at(pg_session, 2025, 3)}
    assert stock["MED0000001"] == Decimal("12")
    activity = queries.customer_activity(pg_session, ["20111111111"], date(2025, 1, 1))
    assert activity["20111111111"]["order_count"] == 2
