from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.modules import MODULES

API_PREFIX = "/api/v1"

app = FastAPI(
    title="VetChain API",
    version="0.1.0",
    description="API de VetChain para Mederi. Contrato en docs/endpoints.md. Errores: {\"error\": {code, message, details}}.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

for module in MODULES.values():
    app.include_router(module.router, prefix=API_PREFIX)


@app.get("/health", tags=["general"])
def health() -> dict:
    """La API está viva."""
    return {"status": "ok"}
