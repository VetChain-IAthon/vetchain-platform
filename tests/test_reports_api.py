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
    for path in ("/dashboard/summary", "/reports", "/reports/kpis", "/reports/sales", "/reports/customers",
                 "/reports/stock", "/reports/receivables", "/reports/salespeople", "/reports/funnel"):
        assert client.get("/api/v1" + path, headers=seller).status_code == 403, path
    bad = client.get("/api/v1/reports/sales?from=2025-04-01&to=2025-03-01", headers=manager)
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_date_range"
