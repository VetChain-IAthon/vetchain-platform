from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SessionLocal


class SqlAlchemyUnitOfWork:
    """Una sesión por caso de uso. `with uow:` abre la sesión y hace rollback de lo que no se confirmó con commit.

    Con `session` usa una sesión ya abierta (la de la petición HTTP, compartida con los repositorios) y no la cierra.
    """

    def __init__(self, session_factory: sessionmaker = SessionLocal, session: Session | None = None) -> None:
        self._session_factory = session_factory
        self._owns_session = session is None
        self.session: Session | None = session

    def __enter__(self) -> "SqlAlchemyUnitOfWork":
        if self._owns_session:
            self.session = self._session_factory()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.rollback()
        finally:
            if self._owns_session:
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
