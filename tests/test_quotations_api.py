"""Flujo HTTP de cotizaciones con SQLite de pruebas, sin escribir en VetChainDb."""
import pytest

from tests.defontana_sample import load_sample

RUC = "20111111111"
LINE = {"product_code": "MED0000001", "quantity": 2}
BODY = {"ruc": RUC, "lines": [LINE], "discount_pct": 5}


@pytest.fixture()
def manager(login, db):
    headers = login("manager")
    load_sample(db)
    return headers


def configure(client, headers):
    assert client.put("/api/v1/settings/pricing", headers=headers, json={
        "igv_rate_pct": 18, "quotation_validity_days": 15, "min_margin_pct": 10,
        "promo_margin_cut_pct": 0,
    }).status_code == 200
    assert client.put("/api/v1/settings/level-thresholds", headers=headers,
                      json={"min_amount_b": 50, "min_amount_a": 120}).status_code == 200
    for level in "ABC":
        assert client.put(f"/api/v1/settings/customer-levels/{level}", headers=headers,
                          json={"max_discount_pct": 10, "margin_pct": 25, "credit_days": 30}).status_code == 200


def test_products_use_latest_non_cancelled_paid_price(client, manager):
    products = client.get("/api/v1/products", headers=manager).json()
    assert products["total"] == 2
    first = client.get("/api/v1/products/MED0000001", headers=manager).json()
    assert first["reference_price"] == 45 and first["reference_price_origin"] == "estimated"
    assert client.get("/api/v1/products/REV0000001", headers=manager).status_code == 404


def test_preview_requires_real_settings_and_shows_no_cost_warning(client, manager):
    missing = client.post("/api/v1/quotation-previews", headers=manager, json=BODY)
    assert missing.status_code == 400 and missing.json()["error"]["code"] == "thresholds_not_configured"
    configure(client, manager)
    result = client.post("/api/v1/quotation-previews", headers=manager, json=BODY)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["subtotal"] == 90 and body["net"] == 85.5
    assert body["igv"] == 15.39 and body["total_with_tax"] == 100.89
    assert body["margin_pct"] is None and body["warnings"] == ["no_cost_data"]
    assert body["approval_required"] is False and body["data_origin"] == "estimated"


def test_issue_approval_and_portfolio_scope(client, manager, login):
    configure(client, manager)
    seller = login("salesperson")
    denied = client.post("/api/v1/quotation-previews", headers=seller, json=BODY)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "outside_portfolio"
    own = {**BODY, "ruc": "10222222222", "discount_pct": 12}
    preview = client.post("/api/v1/quotation-previews", headers=seller, json=own)
    assert preview.status_code == 200 and preview.json()["approval_required"] is True
    assert client.post("/api/v1/quotations", headers=seller, json=own).json()["error"]["code"] == "approval_required"
    forbidden = client.post("/api/v1/quotations", headers=seller,
                            json=own | {"approval_confirmed": True, "approval_note": "Revisado"})
    assert forbidden.status_code == 403
    created = client.post("/api/v1/quotations", headers=manager,
                          json=own | {"approval_confirmed": True, "approval_note": "Revisado"})
    assert created.status_code == 201, created.text
    qid = created.json()["id"]
    other = client.post("/api/v1/quotations", headers=manager, json=BODY)
    assert other.status_code == 201, other.text
    assert client.get(f"/api/v1/quotations/{qid}", headers=seller).status_code == 200
    assert client.get("/api/v1/quotations", headers=seller).json()["total"] == 1
    assert client.get(f"/api/v1/quotations/{other.json()['id']}", headers=seller).status_code == 403
    assert client.get(f"/api/v1/quotations/{qid}", headers=manager).json()["approval_note"] == "Revisado"
