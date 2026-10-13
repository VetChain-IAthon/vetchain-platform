from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.modules import MODULES

app = FastAPI(title="VetChain API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for name, module in MODULES.items():
    app.include_router(module.router, prefix=f"/api/{name}", tags=[name])


@app.get("/health", tags=["general"])
def health() -> dict:
    return {"status": "ok", "modules": list(MODULES)}
