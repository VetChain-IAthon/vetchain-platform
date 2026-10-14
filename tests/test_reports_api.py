"""Reportes HTTP sobre datos aislados de prueba, sin escribir en VetChainDb."""
import pytest

from tests.defontana_sample import load_sample


@pytest.fixture()
def manager(login, db):
    headers = login("manager")
    load_sample(db)
    return headers


def test_dashboard_and_sales_use_core_non_bonus_non_cancelled_orders(client, manager):
    summary = client.get("/api/v1/dashboard/summary", headers=manager)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["period"]["data_as_of"] == "2025-03-01"
    assert data["amount"] == 155 and data["order_count"] == 3
    assert data["average_order"] == 51.67 and data["active_customers"] == 2
    assert data["top_ten_share_pct"] == 100
    assert data["data_origin"] == "real" and "alerts_unavailable" in data["warnings"]

    sales = client.get("/api/v1/reports/sales", headers=manager).json()
    assert sales["amount"] == 155 and sales["margin_pct"] is None
    assert sales["products"][0]["amount"] == 125
    assert sales["categories"] == [{"code": "001", "amount": 155, "data_origin": "real"}]
    assert "no_cost_data" in sales["warnings"]
    assert sales["invoice_discount"] == 5 and sales["list_amount"] == 160  # P2: 10 % de descuento en la línea de 50
    assert [(p["code"], p["below_reference_pct"]) for p in sales["price_points"]] == [("MED0000001", 7.4), ("MED0000002", -50.0)]
    assert sales["below_reference_pct"] == -3.7
    seller = client.get("/api/v1/reports/sales?salesperson_code=002", headers=manager).json()
    assert seller["amount"] == 55 and seller["order_count"] == 2  # P2 y P4, que tomó el vendedor 002

    january = client.get("/api/v1/dashboard/summary?from=2025-01-01&to=2025-01-31", headers=manager).json()
    assert january["amount"] == 100 and january["order_count"] == 1
    assert january["period"]["data_as_of"] == "2025-03-01"


def test_customer_stock_salesperson_and_unavailable_reports(client, manager):
    customers = client.get("/api/v1/reports/customers", headers=manager).json()
    assert customers["master_count"] == 3 and customers["active_count"] == 2
    assert customers["no_orders_12m"] == 1 and customers["at_risk_count"] is None
    assert customers["top_customers"][0]["amount"] == 145

    stock = client.get("/api/v1/reports/stock", headers=manager).json()
    assert stock["stock_as_of"] == "2025-03-31"
    assert "stock_balance_unconfirmed" in stock["warnings"]
    assert next(x for x in stock["items"] if x["product_code"] == "MED0000001")["balance"] == 12
    med1 = next(x for x in stock["items"] if x["product_code"] == "MED0000001")
    # 3 unidades pedidas en 12 meses (sin la bonificada ni el pedido cancelado): 12 alcanzan para 1 460 días
    assert med1["units_12m"] == 3 and med1["last_sale_date"] == "2025-02-15"
    assert med1["coverage_days"] == 1460 and med1["status"] == "overstock"
    assert all(x["product_code"].startswith("MED") for x in stock["items"])

    sellers = client.get("/api/v1/reports/salespeople", headers=manager).json()
    assert sellers["amount"] == 155
    assert {(x["code"], x["amount"]) for x in sellers["items"]} == {("001", 100), ("002", 55)}

    receivables = client.get("/api/v1/reports/receivables", headers=manager).json()
    assert receivables["outstanding_amount"] is None and receivables["warnings"] == ["receipts_not_linked"]
    kpis = client.get("/api/v1/reports/kpis", headers=manager).json()
    assert all(x["target"] is None and x["status"] is None for x in kpis["items"])
    funnel = client.get("/api/v1/reports/funnel", headers=manager).json()
    assert funnel["alerts"] is None and funnel["recovered_amount"] is None
    catalog = client.get("/api/v1/reports", headers=manager).json()
    assert catalog["total"] == 7 and catalog["items"][0]["code"] == "sales"


def test_all_reports_forbid_salesperson_and_reject_bad_period(client, manager, login):
    seller = login("salesperson")
    below = next(x for x in kpis["items"] if x["code"] == "below_reference_pct")
    # MED1 pagado a 41,67 frente a 45 (referencia P2); MED2 a 15 frente a 10 (P4): promedio ponderado por monto
    assert below["value"] == -3.7 and below["data_origin"] == "estimated"
    for path in ("/dashboard/summary", "/reports", "/reports/kpis", "/reports/sales", "/reports/customers",
                 "/reports/stock", "/reports/receivables", "/reports/salespeople", "/reports/funnel"):
        assert client.get("/api/v1" + path, headers=seller).status_code == 403, path
    bad = client.get("/api/v1/reports/sales?from=2025-04-01&to=2025-03-01", headers=manager)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_date_range"
