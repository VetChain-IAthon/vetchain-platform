"""Las secciones simuladas piden sesión (gerencia o vendedor) y siempre declaran su origen."""
from app.core.database import SessionLocal
from app.modules.simulations.infrastructure.orm import SimulatedSectionRow


def test_simulated_sections_require_session_and_are_labeled(client, login):
    with SessionLocal() as db:
        db.add(SimulatedSectionRow(key="kpis", payload={"margin": 28.9}, origin="simulated"))
        db.commit()
    assert client.get("/api/v1/simulated-sections").status_code == 401
    assert client.get("/api/v1/simulated-sections", headers=login("salesperson")).status_code == 200
    response = client.get("/api/v1/simulated-sections", headers=login("manager"))
    assert response.status_code == 200, response.text
    assert response.json() == {"origin": "simulated", "sections": {"kpis": {"margin": 28.9}}}
