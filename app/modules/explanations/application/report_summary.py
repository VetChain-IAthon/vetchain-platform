"""Redacción opcional de reportes con métricas agregadas de lista cerrada."""
from dataclasses import dataclass
from math import isfinite

from app.core.domain import BusinessRuleError
from app.modules.explanations.domain.ports import TextGenerator


METRICS: dict[str, dict[str, str]] = {
    "dashboard": {"amount_pen": "monto de pedidos (PEN sin IGV)", "orders": "pedidos", "active_customers": "clientes con pedido", "average_order_pen": "ticket promedio (PEN)", "top_ten_share_pct": "participación de diez mayores clientes (%)"},
    "kpis": {"indicators": "indicadores", "on_target": "en meta", "attention": "en atención", "critical": "críticos", "missing": "sin dato", "sales_growth_pct": "crecimiento de pedidos (%)"},
    "sales": {"amount_pen": "monto de pedidos (PEN sin IGV)", "orders": "pedidos", "invoice_discount_pen": "descuento en factura (PEN)", "below_reference_pct": "precio bajo referencia (%)"},
    "customers": {"active": "clientes activos", "previous_active": "clientes activos del período anterior", "top_ten_share_pct": "participación de diez mayores clientes (%)", "at_risk": "clientes fuera de su ritmo de compra", "recoverable": "clientes recuperables"},
    "stock": {"products": "productos en kardex", "normal": "stock normal", "overstock": "sobrestock", "slow": "sin pedidos en 90 días", "out_with_demand": "sin stock con pedidos", "coverage_days": "cobertura agregada estimada (días)"},
    "receivables": {"receipts": "cobros registrados", "collected_pen": "importe cobrado (PEN)", "top_five_share_pct": "participación de cinco mayores pagadores (%)"},
    "salespeople": {"salespeople": "vendedores", "leader_share_pct": "participación del vendedor de mayor volumen (%)", "leader_customers": "clientes de ese vendedor", "level_a_customers": "clientes nivel A"},
}

LIMITATIONS = {
    "dashboard": "Son montos de pedidos, no ventas facturadas. No inventes una comparación semanal.",
    "kpis": "Las metas son propuestas por validar; no asumas resultados para indicadores sin dato.",
    "sales": "Son montos de pedidos, no ventas facturadas. No afirmes utilidad sin costos validados.",
    "customers": "Son agregados. No identifiques clientes ni propongas acciones individuales.",
    "stock": "El saldo del kardex está por confirmar; no hay datos de lotes, vencimientos ni costos.",
    "receivables": "Los cobros no están enlazados con facturas; no infieras deuda ni vencimientos.",
    "salespeople": "La cartera es provisional; no identifiques vendedores ni infieras resultados de alertas.",
}


@dataclass(frozen=True)
class ReportSummary:
    text: str
    source: str


class ExplainReport:
    def __init__(self, generator: TextGenerator) -> None:
        self.generator = generator

    def execute(self, report: str, metrics: dict[str, float]) -> ReportSummary:
        allowed = METRICS.get(report)
        if not allowed or not metrics or set(metrics) - set(allowed) or len(metrics) > 12:
            raise BusinessRuleError("Las métricas del reporte no son válidas.", "invalid_report_metrics")
        if any(not isfinite(value) or abs(value) > 1_000_000_000_000 for value in metrics.values()):
            raise BusinessRuleError("Las métricas contienen cantidades inválidas.", "invalid_report_metrics")
        facts = "\n".join(f"- {allowed[key]}: {metrics[key]}" for key in allowed if key in metrics)
        prompt = (
            "Redacta en español un resumen ejecutivo breve (máximo tres frases) del reporte "
            f"{report}. Usa solamente las métricas agregadas siguientes:\n{facts}\n"
            f"Límites: {LIMITATIONS[report]} No inventes causas, pronósticos, recomendaciones "
            "ni cifras faltantes. No menciones nombres ni identificadores de personas."
        )
        try:
            text = self.generator.generate(prompt).strip()
            if text:
                return ReportSummary(text, "gemini")
        except Exception:
            pass
        return ReportSummary("Gemini no pudo redactar este resumen. Las cifras calculadas del reporte siguen disponibles.", "fallback")
