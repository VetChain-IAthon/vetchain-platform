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


def test_at_risk_customers(client, manager):
    # Corte 2025-03-01. VET UNO: pedidos el 10-01 y 15-02 (ritmo 36 días), última hace 14 días: activo.
    # MARIA: un solo pedido el 01-03 (ritmo por defecto 30 días), 0 días: activo.
    body = client.get("/api/v1/customers/at-risk", headers=manager).json()
    assert body["total"] == 0 and body["items"] == []
    assert body["data_origin"] == "estimated" and body["warning"] == "risk_factors_provisional"
    assert body["at_risk_factor"] == 1.5 and body["default_rhythm_days"] == 30


def test_at_risk_customer_listed(client, manager, db):
    from app.infrastructure.loaders.defontana_csv import load_source
    from tests.defontana_sample import SPEC

    # Pedidos cada 10 días; el último, 20 días antes del corte (2× su ritmo): en riesgo.
    load_source(db, SPEC["customers"], [["20444444444", "VET RIESGO S.A.C.", "AV. 4", "", "", "002", "X", "015", "LIMA", "006", "", "001", "0.00", "0.00", "1", "0.00"]])
    orders = [("R1", "2025-01-20", "40.00"), ("R2", "2025-01-30", "40.00"), ("R3", "2025-02-09", "40.00")]
    load_source(db, SPEC["orders"], [[no, day, "20444444444", "VET RIESGO", "002", "ANA", "001", amount, "0.00", "7.20", "47.20", "T"] for no, day, amount in orders])
    load_source(db, SPEC["order_lines"], [[no, day, "20444444444", "002", "1", "MED0000001", "X", "001", "1", "1", "1", "40.0000000000", "0.00", "40.00"] for no, day, _ in orders])
    db.commit()

    item, = client.get("/api/v1/customers/at-risk", headers=manager).json()["items"]
    assert item["ruc"] == "20444444444" and item["days_since_last_order"] == 20
    assert item["purchase_rhythm_days"] == 10 and item["money_at_stake"] == 40

    def follow_up():
        body = client.get("/api/v1/customers/at-risk/follow-up", headers=manager).json()
        assert body["data_origin"] == "estimated" and body["warning"] == "portfolio_provisional"
        return body["items"]

    seller, = follow_up()
    assert seller["salesperson_code"] == "002" and seller["salesperson_name"] == "Ana Rios"
    assert seller["buckets"] == [{"outcome": None, "customer_count": 1, "money_at_stake": 40}]
    client.post("/api/v1/customers/20444444444/contacts", headers=manager, json={"outcome": "Pidió cotización"})
    assert follow_up()[0]["buckets"] == [{"outcome": "Pidió cotización", "customer_count": 1, "money_at_stake": 40}]


def test_customer_brief_uses_real_orders_and_flags_what_is_pending(client, manager, login):
    body = client.get("/api/v1/customers/20111111111/brief", headers=manager).json()
    assert body["date_from"] == "2024-03-02" and body["date_to"] == "2025-03-01" and body["projection"] == "month"
    # P3 está cancelado y la revista no es veterinaria: no suman; P1 tiene una línea bonificada
    assert body["amount"] == 145.0 and body["order_count"] == 2 and body["average_order_amount"] == 72.5
    assert body["rank"] == 1 and body["ranked_customers"] == 2 and body["share_pct"] == 93.5
    assert body["salesperson_name"] == "Oficina" and body["salesperson_share_pct"] == 69.0
    assert body["purchase_rhythm_days"] == 36.0 and body["last_order_date"] == "2025-02-15"
    assert body["days_since_last_order"] == 14 and body["days_late"] == 0
    assert body["expected_next_order_date"] == "2025-03-23"
    assert body["invoice_discount"] == 5.0 and body["list_amount"] == 150.0
    assert len(body["monthly"]) == 13 and body["monthly"][-3] == {"month": "2025-01", "amount": 100.0, "order_count": 1}
    first = body["products"][0]
    assert first["product_code"] == "MED0000001" and first["quantity"] == 3 and first["average_price"] == 41.67
    assert first["reference_price"] == 45.0 and first["below_reference_pct"] == 7.4
    assert body["projected_amount"] is None and body["estimated_profit"] is None
    assert {"projection_unavailable", "no_cost_data", "ai_unavailable", "thresholds_not_configured"} <= set(body["warnings"])

    narrow = client.get("/api/v1/customers/20111111111/brief?from=2025-02-01&to=2025-02-28&projection=year", headers=manager).json()
    assert narrow["amount"] == 45.0 and narrow["order_count"] == 1 and narrow["purchase_rhythm_days"] is None
    assert narrow["projection"] == "year" and narrow["days_since_last_order"] == 13

    bad = client.get("/api/v1/customers/20111111111/brief?from=2025-03-01&to=2025-01-01", headers=manager)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_period"
    assert client.get("/api/v1/customers/20111111111/brief?projection=week", headers=manager).status_code == 422
    assert client.get("/api/v1/customers/20111111111/brief", headers=login("salesperson")).status_code == 403
