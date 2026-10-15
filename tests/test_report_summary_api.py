from app.modules.explanations.interface import dependencies as deps


def test_report_summary_is_manager_only_and_rejects_unknown_metrics(client, login, monkeypatch):
    class Generator:
        def generate(self, prompt):
            return "Resumen redactado."

    monkeypatch.setattr(deps, "text_generator", lambda: Generator())
    url = "/api/v1/insights/report-summary"
    payload = {"report": "sales", "metrics": {"amount_pen": 1234.5}}
    assert client.post(url, json=payload).status_code == 401
    assert client.post(url, json=payload, headers=login("salesperson")).status_code == 403
    manager = login("manager")
    response = client.post(url, json=payload, headers=manager)
    assert response.status_code == 200
    assert response.json() == {"text": "Resumen redactado.", "source": "gemini"}
    bad = client.post(url, json={"report": "sales", "metrics": {"customer_id": 123}}, headers=manager)
    assert bad.status_code == 400
