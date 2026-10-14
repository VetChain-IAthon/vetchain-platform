"""Rutas generales: /health, rutas del contrato aún pendientes (501) y errores de ruta."""
from fastapi.testclient import TestClient


def test_health_needs_no_session(client: TestClient):
    assert client.get("/health").json() == {"status": "ok"}


def test_pending_routes_answer_501_after_auth_and_role(client, login):
    assert client.get("/api/v1/alerts").status_code == 401
    seller = login("salesperson")
    response = client.get("/api/v1/alerts", headers=seller)
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"
    assert client.get("/api/v1/reports/kpis", headers=seller).status_code == 403  # solo gerencia
    manager = login("manager")
    assert client.patch("/api/v1/import-suggestions/1", headers=manager).status_code == 501


def test_unknown_route_uses_standard_error(client):
    response = client.get("/api/v1/no-existe")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "not_found", "message": "La ruta no existe.", "details": None}}
