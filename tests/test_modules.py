from app.modules import MODULES


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert set(r.json()["modules"]) == set(MODULES)


def test_each_module_returns_status(client):
    for name in MODULES:
        r = client.get(f"/api/{name}/status")
        assert r.status_code == 200, name
        assert r.json()["module"] == name
