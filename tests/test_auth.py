import pytest

from app.modules.auth import service


def test_login_and_me(client, db):
    service.create_user(db, "gerente@mederi.pe", "clave-segura-1", "management")
    r = client.post("/api/auth/login", json={"email": "gerente@mederi.pe", "password": "clave-segura-1"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "management"


def test_login_with_wrong_password(client, db):
    service.create_user(db, "vendedor@mederi.pe", "clave-segura-1", "sales_rep")
    r = client.post("/api/auth/login", json={"email": "vendedor@mederi.pe", "password": "otra"})
    assert r.status_code == 401


def test_me_without_session(client):
    assert client.get("/api/auth/me").status_code == 401


def test_create_user_with_invalid_role(db):
    with pytest.raises(ValueError):
        service.create_user(db, "compras@mederi.pe", "clave-segura-1", "purchasing")
