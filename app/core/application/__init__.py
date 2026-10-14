"""Núcleo compartido, parte de aplicación: tipos que usan los casos de uso de todos los módulos."""
from app.core.application.paging import Page, Paging
from app.core.application.session_user import MANAGER, SALESPERSON, SessionUser

__all__ = ["MANAGER", "Page", "Paging", "SALESPERSON", "SessionUser"]
