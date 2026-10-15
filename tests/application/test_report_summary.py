import pytest

from app.modules.explanations.application.report_summary import ExplainReport


class Generator:
    def generate(self, prompt):
        assert "monto de pedidos" in prompt
        assert "1234.5" in prompt
        assert "nombre" not in prompt.lower().split("métricas agregadas siguientes:")[1].split("límites:")[0]
        return "Los pedidos sumaron 1234,5 soles."


def test_only_allowlisted_numeric_facts_reach_generator():
    result = ExplainReport(Generator()).execute("sales", {"amount_pen": 1234.5})
    assert result.source == "gemini"


def test_unknown_metric_is_rejected():
    with pytest.raises(Exception, match="métricas"):
        ExplainReport(Generator()).execute("sales", {"customer_name": 123})


def test_generator_failure_is_labeled():
    class Failing:
        def generate(self, prompt):
            raise RuntimeError()

    assert ExplainReport(Failing()).execute("kpis", {"indicators": 12}).source == "fallback"


def test_figures_are_rounded_before_reaching_generator():
    class Capture:
        def generate(self, prompt):
            self.prompt = prompt
            return "ok"

    capture = Capture()
    ExplainReport(capture).execute("kpis", {"indicators": 12.0, "sales_growth_pct": -8.834165289937118})
    assert "indicadores: 12\n" in capture.prompt
    assert "crecimiento de pedidos (%): -8.83" in capture.prompt
