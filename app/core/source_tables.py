"""Re-export para compatibilidad. El código nuevo importa de app.infrastructure.db.source_models."""
from app.infrastructure.db.source_models import (  # noqa: F401
    AMOUNT,
    SOURCE_MODELS,
    Customer,
    Order,
    OrderLine,
    Product,
    Receipt,
    Salesperson,
    StockBalance,
)

PEN = AMOUNT  # nombre usado por los modelos planos anteriores
