"""Interfaz de customers (fase 1): /customers y sus subrecursos, con los datos de ejemplo de Defontana."""
import pytest

from tests.defontana_sample import load_sample

THRESHOLDS = {"min_amount_b": 50, "min_amount_a": 120}
RULE = {"max_discount_pct": 5, "margin_pct": 25, "credit_days": 30}


@pytest.fixture()
def manager(login, db):
    headers = login("manager")
    load_sample(db)
    return headers


def test_list_without_thresholds_has_no_level(client, manager):
    body = client.get("/api/v1/customers", headers=manager).json()
    assert body["total"] == 3 and body["levels_configured"] is False
    assert body["data_as_of"] == "2025-03-01" and body["data_origin"] == "real"
    first = body["items"][0]
    # P3 está cancelado y la revista no es veterinaria: no suman
    assert first["ruc"] == "20111111111" and first["amount_12m"] == 145.01 and first["level"] is None
    assert first["order_count_12m"] == 2 and first["last_order_date"] == "2025-02-15"
    assert sum(item["share_pct"] for item in body["items"]) == pytest.approx(100, abs=0.2)
    filtered = client.get("/api/v1/customers?level=A", headers=manager)
    assert filtered.status_code == 400 and filtered.json()["error"]["code"] == "thresholds_not_configured"


def test_list_with_levels_search_and_paging(client, manager):
    client.put("/api/v1/settings/level-thresholds", headers=manager, json=THRESHOLDS)
    body = client.get("/api/v1/customers", headers=manager).json()
    assert [(i["ruc"], i["level"]) for i in body["items"]] == [("20111111111", "A"), ("10222222222", "C"), ("12345678", "C")]
    assert client.get("/api/v1/customers?level=C", headers=manager).json()["total"] == 2
    assert client.get("/api/v1/customers?search=maria", headers=manager).json()["items"][0]["ruc"] == "10222222222"
    page = client.get("/api/v1/customers?per_page=1&page=2", headers=manager).json()
    assert page["total"] == 3 and [i["ruc"] for i in page["items"]] == ["10222222222"]
    assert client.get("/api/v1/customers?level=Z", headers=manager).status_code == 422


def test_salesperson_sees_only_own_portfolio(client, manager, login):
    seller = login("salesperson")  # vendedor 002
    body = client.get("/api/v1/customers?salesperson_code=001", headers=seller).json()
    assert {i["ruc"] for i in body["items"]} == {"10222222222", "12345678"}
    denied = client.get("/api/v1/customers/20111111111", headers=seller)
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "outside_portfolio"
    assert client.get("/api/v1/customers?salesperson_code=001", headers=manager).json()["total"] == 1


def test_customer_detail_orders_and_products(client, manager):
    detail = client.get("/api/v1/customers/20111111111", headers=manager).json()
    assert detail["phone"] == "987654321" and detail["lifetime_order_count"] == 2
    assert detail["first_order_date"] == "2025-01-10" and detail["purchase_rhythm_days"] == 36.0
    assert detail["average_order_amount_12m"] == 72.51
    assert client.get("/api/v1/customers/99999999999", headers=manager).status_code == 404
    assert client.get("/api/v1/customers/abc", headers=manager).json()["error"]["code"] == "invalid_ruc"
    orders = client.get("/api/v1/customers/20111111111/orders", headers=manager).json()
    assert [o["order_no"] for o in orders["items"]] == ["P3", "P2", "P1"]  # el historial muestra todos los estados
    products = client.get("/api/v1/customers/20111111111/products", headers=manager).json()["items"]
    assert [p["product_code"] for p in products] == ["MED0000001", "MED0000002"]


def test_commercial_terms_need_settings(client, manager):
    url = "/api/v1/customers/20111111111/commercial-terms"
    assert client.get(url, headers=manager).json()["error"]["code"] == "thresholds_not_configured"
    client.put("/api/v1/settings/level-thresholds", headers=manager, json=THRESHOLDS)
    assert client.get(url, headers=manager).json()["error"]["code"] == "levels_not_configured"
    for level in "ABC":
        client.put(f"/api/v1/settings/customer-levels/{level}", headers=manager, json=RULE | {"credit_days": 60 if level == "A" else 30})
    terms = client.get(url, headers=manager).json()
    assert terms["level"] == "A" and terms["credit_days"] == 60 and terms["amount_12m"] == 145.01


def test_contacts_flow(client, manager):
    url = "/api/v1/customers/20111111111/contacts"
    assert client.post(url, headers=manager, json={"outcome": ""}).status_code == 422
    created = client.post(url, headers=manager, json={"outcome": "Pidió cotización"})
    assert created.status_code == 201 and created.json()["outcome"] == "Pidió cotización"
    listed = client.get(url, headers=manager).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == created.json()["id"]


def test_whatsapp_link(client, manager):
    link = client.get("/api/v1/customers/20111111111/whatsapp-link", headers=manager).json()
    assert link["url"].startswith("https://wa.me/51987654321?text=") and "VET UNO S.A.C." in link["message"]
    custom = client.get("/api/v1/customers/20111111111/whatsapp-link?message=Hola", headers=manager).json()
    assert custom["url"].endswith("text=Hola")
    no_phone = client.get("/api/v1/customers/10222222222/whatsapp-link", headers=manager)
    assert no_phone.status_code == 400 and no_phone.json()["error"]["code"] == "invalid_whatsapp_phone"


def test_dormant_customers(client, manager, db):
    from app.infrastructure.loaders.defontana_csv import load_source
    from tests.defontana_sample import SPEC

    # Cliente con pedidos solo antes de la ventana de 12 meses (corte 2025-03-01).
    load_source(db, SPEC["customers"], [["20333333333", "VET ANTIGUA S.A.C.", "AV. 3", "", "", "002", "X", "015", "CUSCO", "006", "", "001", "0.00", "0.00", "1", "0.00"]])
    load_source(db, SPEC["orders"], [["P0", "2023-05-02", "20333333333", "VET ANTIGUA", "002", "ANA", "001", "30.00", "0.00", "5.40", "35.40", "T"]])
    load_source(db, SPEC["order_lines"], [["P0", "2023-05-02", "20333333333", "002", "1", "MED0000001", "X", "001", "1", "1", "1", "30.0000000000", "0.00", "30.00"]])
    db.commit()

    body = client.get("/api/v1/customers/dormant", headers=manager).json()
    assert body["customer_count"] == 4 and body["dormant_count"] == 2 and body["ordered_before_count"] == 1
    assert body["data_as_of"] == "2025-03-01" and body["data_origin"] == "real"
    assert [i["ruc"] for i in body["items"]] == ["20333333333", "12345678"]  # por monto histórico
    first, never = body["items"]
    assert first["order_count"] == 1 and first["lifetime_amount"] == 30 and first["last_order_date"] == "2023-05-02"
    assert never["order_count"] == 0 and never["last_order_date"] is None
    assert body["type_counts"] == {"all": 2, "company": 1, "person": 0}

    assert client.get("/api/v1/customers/dormant?search=cusco", headers=manager).json()["total"] == 1
    companies = client.get("/api/v1/customers/dormant?customer_type=company", headers=manager).json()
    assert [i["ruc"] for i in companies["items"]] == ["20333333333"] and companies["type_counts"]["all"] == 2
    assert client.get("/api/v1/customers/dormant?customer_type=x", headers=manager).status_code == 422
