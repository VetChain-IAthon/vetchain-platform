"""La comparación conserva el control de rol y el formato del contrato HTTP."""
from app.main import app
from app.modules.prediction.application.use_cases import ForecastComparison, ForecastExplanation
from app.modules.prediction.interface.dependencies import get_compare_forecasts, get_explain_forecast


class FakeComparison:
    def execute(self, product_id, scenario, horizon, cutoff):
        assert (product_id, scenario, horizon) == ("P1", "B", 3)
        return ForecastComparison("P1", "B", 3, "2024-12", "2025-01", 28.5, 25.25, 28.33)


def test_forecast_is_manager_only_and_returns_comparison(client, login):
    app.dependency_overrides[get_compare_forecasts] = lambda: FakeComparison()
    try:
        assert client.get("/api/v1/prediction/forecasts", params={"product_id": "P1"}).status_code == 401
        seller = login("salesperson")
        assert client.get("/api/v1/prediction/forecasts", params={"product_id": "P1"}, headers=seller).status_code == 403
        manager = login("manager")
        response = client.get("/api/v1/prediction/forecasts", params={"product_id": "P1", "scenario": "B", "horizon": 3}, headers=manager)
        assert response.status_code == 200, response.text
        assert response.json()["extra_trees"] == 25.25
        assert response.json()["moving_average_6m"] == 28.5
        assert response.json()["predictive_model"] == 28.33
    finally:
        app.dependency_overrides.pop(get_compare_forecasts, None)


def test_forecast_explanation_requires_manager_and_reports_source(client, login):
    class FakeExplanation:
        def execute(self, product_id, scenario, horizon, cutoff):
            assert (product_id, scenario, horizon) == ("P1", "A", 1)
            return ForecastExplanation("Explicación de prueba.", "gemini")

    app.dependency_overrides[get_explain_forecast] = lambda: FakeExplanation()
    payload = {"product_id": "P1", "scenario": "A", "horizon": 1}
    try:
        url = "/api/v1/prediction/forecasts/explanation"
        assert client.post(url, json=payload).status_code == 401
        assert client.post(url, json=payload, headers=login("salesperson")).status_code == 403
        response = client.post(url, json=payload, headers=login("manager"))
        assert response.status_code == 200, response.text
        assert response.json() == {"text": "Explicación de prueba.", "source": "gemini"}
    finally:
        app.dependency_overrides.pop(get_explain_forecast, None)
