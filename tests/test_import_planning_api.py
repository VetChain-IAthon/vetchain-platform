"""La simulación debe ser visible a gerencia y sus decisiones deben persistir."""
from app.modules.import_planning.infrastructure.orm import ImportLaboratoryRow, ImportSuggestionRow


def test_four_demo_labs_and_review_decision(client, db, login):
    manager = login("manager")
    db.add_all([ImportLaboratoryRow(id=i, name=f"Laboratorio {i}", country="Ejemplo", lead_days=60,
                                    import_cost_usd=100, is_demo=True) for i in range(1, 5)])
    db.add(ImportSuggestionRow(id=1, laboratory_id=1, product_name="Producto de ejemplo", stock_units=10,
                               coverage_days=20, demand_90_days=30, suggested_units=25, shelf_life_months=9,
                               days_until_order=2, unit_price_usd=4, decision="pending", is_demo=True))
    db.commit()

    response = client.get("/api/v1/import-suggestions", headers=manager)
    assert response.status_code == 200
    plan = response.json()
    assert plan["data_origin"] == "simulated"
    assert len(plan["laboratories"]) == 4
    assert plan["laboratories"][0]["merchandise_cost_usd"] == "100.00"

    reviewed = client.patch("/api/v1/import-suggestions/1", headers=manager, json={"decision": "approved"})
    assert reviewed.status_code == 200 and reviewed.json()["decision"] == "approved"
    assert db.get(ImportSuggestionRow, 1).decision == "approved"
    assert client.patch("/api/v1/import-suggestions/1", headers=manager,
                        json={"decision": "rejected"}).status_code == 409
    assert client.patch("/api/v1/import-suggestions/1", headers=manager,
                        json={"decision": "pending"}).status_code == 200


def test_only_manager_can_review_demo(client, db, login):
    salesperson = login("salesperson")
    assert client.get("/api/v1/import-suggestions", headers=salesperson).status_code == 403
    assert client.patch("/api/v1/import-suggestions/1", headers=salesperson,
                        json={"decision": "approved"}).status_code == 403
