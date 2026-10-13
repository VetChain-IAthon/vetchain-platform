"""Registro de módulos. Para agregar uno: crear la carpeta con router.py y sumarlo aquí."""
from app.modules import (
    auth,
    customers,
    data_import,
    explanations,
    planning,
    prediction,
    pricing,
    quotes,
    reports,
)

MODULES = {
    "auth": auth,
    "customers": customers,
    "explanations": explanations,
    "pricing": pricing,
    "quotes": quotes,
    "prediction": prediction,
    "reports": reports,
    "planning": planning,
    "data-import": data_import,
}
