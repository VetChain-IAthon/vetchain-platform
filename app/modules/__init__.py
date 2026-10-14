"""Registro de módulos. Cada módulo expone su router en interface/router.py; main.py los monta bajo /api/v1."""
from app.modules.auth.interface import router as auth
from app.modules.customers.interface import router as customers
from app.modules.data_imports.interface import router as data_imports
from app.modules.explanations.interface import router as explanations
from app.modules.import_planning.interface import router as import_planning
from app.modules.prediction.interface import router as prediction
from app.modules.quotations.interface import router as quotations
from app.modules.reports.interface import router as reports
from app.modules.settings.interface import router as settings

MODULES = {
    "auth": auth,
    "customers": customers,
    "explanations": explanations,
    "settings": settings,
    "quotations": quotations,
    "prediction": prediction,
    "reports": reports,
    "import_planning": import_planning,
    "data_imports": data_imports,
}
