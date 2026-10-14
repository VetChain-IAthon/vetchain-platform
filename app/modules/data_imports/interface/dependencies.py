"""Cableado de data_imports: único lugar de la interfaz que ve la infraestructura."""
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.modules.data_imports.application import use_cases as uc
from app.modules.data_imports.infrastructure.repositories import DefontanaSourceLoader, SqlDataImportRepository, SqlSourceStats


def _uow(db: Session) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session=db)


def get_list_sources(db: Session = Depends(get_db)) -> uc.ListDataSources:
    return uc.ListDataSources(SqlDataImportRepository(db), SqlSourceStats(db), _uow(db))


def get_stage_import(db: Session = Depends(get_db)) -> uc.StageImport:
    repo = SqlDataImportRepository(db)
    return uc.StageImport(repo, repo, DefontanaSourceLoader(db), SystemClock(), _uow(db))


def get_list_imports(db: Session = Depends(get_db)) -> uc.ListImports:
    return uc.ListImports(SqlDataImportRepository(db), _uow(db))


def get_get_import(db: Session = Depends(get_db)) -> uc.GetImport:
    return uc.GetImport(SqlDataImportRepository(db), _uow(db))


def get_decide_import(db: Session = Depends(get_db)) -> uc.DecideImport:
    repo = SqlDataImportRepository(db)
    return uc.DecideImport(repo, repo, DefontanaSourceLoader(db), SystemClock(), _uow(db))


def get_preview_import(db: Session = Depends(get_db)) -> uc.PreviewImport:
    repo = SqlDataImportRepository(db)
    return uc.PreviewImport(repo, repo, DefontanaSourceLoader(db), _uow(db))
