from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal


class SqlAlchemyUnitOfWork:
    """Una sesión por caso de uso. `with uow:` abre la sesión y hace rollback si no se llamó a commit."""

    def __init__(self, session_factory: sessionmaker = SessionLocal) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.rollback()
        finally:
            self.session.close()
            self.session = None

    def commit(self) -> None:
        self._require_session().commit()

    def rollback(self) -> None:
        self._require_session().rollback()

    def _require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("La unidad de trabajo no está abierta: usa `with uow:`.")
        return self.session
