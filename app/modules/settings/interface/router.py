from fastapi import APIRouter, Depends

from app.core.application import MANAGER, SALESPERSON, SessionUser
from app.core.auth import require_role
from app.modules.settings.application import use_cases as uc
from app.modules.settings.interface import dependencies as deps
from app.modules.settings.interface.schemas import (
    CustomerLevelIn,
    CustomerLevelOut,
    CustomerLevelsOut,
    LevelThresholdsIn,
    LevelThresholdsOut,
    PricingIn,
    PricingOut,
)

router = APIRouter(prefix="/settings", tags=["ajustes"])
manager_only = require_role(MANAGER)
any_role = require_role(MANAGER, SALESPERSON)


@router.get("/pricing", response_model=PricingOut)
def get_pricing(_: SessionUser = Depends(manager_only), use_case: uc.GetPricing = Depends(deps.get_get_pricing)):
    """IGV, días de vigencia de la cotización, margen mínimo y rebaja de margen en promociones."""
    return PricingOut.from_domain(use_case.execute())


@router.put("/pricing", response_model=PricingOut)
def replace_pricing(
    body: PricingIn, _: SessionUser = Depends(manager_only), use_case: uc.ReplacePricing = Depends(deps.get_replace_pricing)
):
    command = uc.ReplacePricingCommand(
        body.igv_rate_pct, body.quotation_validity_days, body.min_margin_pct, body.promo_margin_cut_pct
    )
    return PricingOut.from_domain(use_case.execute(command))


@router.get("/customer-levels", response_model=CustomerLevelsOut)
def list_customer_levels(
    _: SessionUser = Depends(any_role), use_case: uc.ListCustomerLevels = Depends(deps.get_list_customer_levels)
):
    """Niveles A, B y C con descuento máximo, margen y días de crédito."""
    view = use_case.execute()
    return CustomerLevelsOut(
        items=[CustomerLevelOut.from_domain(rule) for rule in view.rules],
        missing_levels=[level.value for level in view.missing],
    )


@router.put("/customer-levels/{level}", response_model=CustomerLevelOut)
def replace_customer_level(
    level: str,
    body: CustomerLevelIn,
    _: SessionUser = Depends(manager_only),
    use_case: uc.ReplaceCustomerLevel = Depends(deps.get_replace_customer_level),
):
    command = uc.ReplaceCustomerLevelCommand(level, body.max_discount_pct, body.margin_pct, body.credit_days)
    return CustomerLevelOut.from_domain(use_case.execute(command))


@router.get("/level-thresholds", response_model=LevelThresholdsOut)
def get_level_thresholds(
    _: SessionUser = Depends(manager_only), use_case: uc.GetLevelThresholds = Depends(deps.get_get_level_thresholds)
):
    """Montos de pedidos en 12 meses (sin IGV) a partir de los cuales un cliente es B o A."""
    return LevelThresholdsOut.from_domain(use_case.execute())


@router.put("/level-thresholds", response_model=LevelThresholdsOut)
def replace_level_thresholds(
    body: LevelThresholdsIn,
    _: SessionUser = Depends(manager_only),
    use_case: uc.ReplaceLevelThresholds = Depends(deps.get_replace_level_thresholds),
):
    command = uc.ReplaceLevelThresholdsCommand(body.min_amount_b, body.min_amount_a)
    return LevelThresholdsOut.from_domain(use_case.execute(command))
