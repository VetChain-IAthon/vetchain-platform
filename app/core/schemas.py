"""Tipos compartidos por los esquemas HTTP (capa de interfaz)."""
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Dinero y porcentajes: Decimal adentro, número en el JSON (Pydantic v2 los serializaría como texto).
JsonNumber = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]
