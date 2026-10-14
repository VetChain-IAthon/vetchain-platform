"""Adaptadores a las fachadas públicas de settings y customers."""
from app.core.application import SessionUser
from app.core.domain import Percentage, Ruc
from app.modules.quotations.domain.value_objects import CustomerTerms, Level, PricingTerms
import app.modules.customers.application.public as customers_public
import app.modules.settings.application.public as settings_public


class CustomerPublicGateway:
    def __init__(self, user: SessionUser) -> None:
        self.user = user

    def terms_for(self, ruc: Ruc) -> CustomerTerms:
        terms = customers_public.get_commercial_terms(ruc.value, self.user)
        return CustomerTerms(Level(terms.level), Percentage(terms.max_discount_pct),
                             Percentage(terms.margin_pct), terms.credit_days)

    def ensure_access(self, ruc: Ruc) -> None:
        customers_public.ensure_customer_access(ruc.value, self.user)


class SettingsPublicGateway:
    def pricing_terms(self) -> PricingTerms:
        pricing = settings_public.get_pricing()
        return PricingTerms(Percentage(pricing.igv_rate_pct), pricing.quotation_validity_days,
                            Percentage(pricing.min_margin_pct))
