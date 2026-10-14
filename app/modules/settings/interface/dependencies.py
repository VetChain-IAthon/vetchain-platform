"""Cableado de settings: único lugar de la interfaz que ve la infraestructura."""
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.settings.application import public
from app.modules.settings.application import use_cases as uc
from app.modules.settings.infrastructure.repositories import SqlAlchemySettingsRepository


def _build(use_case_class):
    def _dependency(db: Session = Depends(get_db)):
        return use_case_class(SqlAlchemySettingsRepository(db), SqlAlchemyUnitOfWork(session=db))

    return _dependency


get_get_pricing = _build(uc.GetPricing)
get_replace_pricing = _build(uc.ReplacePricing)
get_list_customer_levels = _build(uc.ListCustomerLevels)
get_replace_customer_level = _build(uc.ReplaceCustomerLevel)
get_get_level_thresholds = _build(uc.GetLevelThresholds)
get_replace_level_thresholds = _build(uc.ReplaceLevelThresholds)


@contextmanager
def _scope() -> Iterator[tuple[SqlAlchemySettingsRepository, SqlAlchemyUnitOfWork]]:
    with SessionLocal() as db:
        yield SqlAlchemySettingsRepository(db), SqlAlchemyUnitOfWork(session=db)


public.configure(_scope)
