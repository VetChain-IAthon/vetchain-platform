"""Interfaz de settings: /settings/*."""
PRICING = {"igv_rate_pct": 18, "quotation_validity_days": 15, "min_margin_pct": 20, "promo_margin_cut_pct": 5}


def test_pricing_flow(client, login):
    headers = login("manager")
    response = client.get("/api/v1/settings/pricing", headers=headers)
    assert response.status_code == 404 and response.json()["error"]["code"] == "pricing_not_configured"
    assert client.put("/api/v1/settings/pricing", headers=headers, json=PRICING).status_code == 200
    assert client.get("/api/v1/settings/pricing", headers=headers).json() == PRICING  # números, no texto
    bad = client.put("/api/v1/settings/pricing", headers=headers, json=PRICING | {"igv_rate_pct": 120})
    assert bad.status_code == 422


def test_customer_levels(client, login):
    manager, seller = login("manager"), login("salesperson")
    assert client.get("/api/v1/settings/customer-levels", headers=seller).json() == {"items": [], "missing_levels": ["A", "B", "C"]}
    rule = {"max_discount_pct": 10, "margin_pct": 25, "credit_days": 60}
    assert client.put("/api/v1/settings/customer-levels/a", headers=manager, json=rule).json()["level"] == "A"
    assert client.put("/api/v1/settings/customer-levels/A", headers=seller, json=rule).status_code == 403
    assert client.put("/api/v1/settings/customer-levels/Z", headers=manager, json=rule).status_code == 404
    levels = client.get("/api/v1/settings/customer-levels", headers=seller).json()
    assert [item["level"] for item in levels["items"]] == ["A"] and levels["missing_levels"] == ["B", "C"]


def test_level_thresholds(client, login):
    headers = login("manager")
    assert client.get("/api/v1/settings/level-thresholds", headers=headers).status_code == 404
    bad = client.put("/api/v1/settings/level-thresholds", headers=headers, json={"min_amount_b": 5000, "min_amount_a": 1000})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_thresholds"
    ok = client.put("/api/v1/settings/level-thresholds", headers=headers, json={"min_amount_b": 10000, "min_amount_a": 50000})
    assert ok.status_code == 200


def test_settings_are_manager_only_except_levels(client, login):
    seller = login("salesperson")
    for path in ("/api/v1/settings/pricing", "/api/v1/settings/level-thresholds"):
        assert client.get(path, headers=seller).status_code == 403
