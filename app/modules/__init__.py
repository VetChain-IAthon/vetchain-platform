"""Registro de módulos. Cada módulo expone su router en interface/router.py; main.py los monta bajo /api/v1."""
from app.modules.auth.interface import router as auth_router
from app.modules.customers.interface import router as customers_router
from app.modules.data_imports.interface import router as data_imports_router
from app.modules.explanations.interface import router as explanations_router
from app.modules.import_planning.interface import router as import_planning_router
from app.modules.messaging.interface import router as messaging_router
from app.modules.prediction.interface import router as prediction_router
from app.modules.quotations.interface import router as quotations_router
from app.modules.reports.interface import router as reports_router
from app.modules.settings.interface import router as settings_router
from app.modules.simulations.interface import router as simulations_router

MODULES = {
    "auth": auth_router,
    "customers": customers_router,
    "explanations": explanations_router,
    "settings": settings_router,
    "quotations": quotations_router,
    "prediction": prediction_router,
    "reports": reports_router,
    "import_planning": import_planning_router,
    "data_imports": data_imports_router,
    "messaging": messaging_router,
    "simulations": simulations_router,
}
