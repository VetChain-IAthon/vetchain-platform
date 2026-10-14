"""Interfaz de auth: /sessions, /me y /users."""
from tests.conftest import PASSWORD


def test_login_and_me(client, login):
    headers = login("manager", "gerente@mederi.pe")
    me = client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json() | {"id": 0} == {
        "id": 0, "email": "gerente@mederi.pe", "full_name": "Usuario manager", "phone": None,
        "role": "manager", "salesperson_code": None, "active": True,
    }


def test_login_returns_user_and_bearer_token(client, login):
    login("salesperson", "vende@mederi.pe")
    response = client.post("/api/v1/sessions", json={"email": "VENDE@mederi.pe", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer" and body["user"]["salesperson_code"] == "002"


def test_wrong_password_is_401_with_standard_error(client, login):
    login("manager", "gerente@mederi.pe")
    response = client.post("/api/v1/sessions", json={"email": "gerente@mederi.pe", "password": "otra"})
    assert response.status_code == 401
    assert response.json() == {
        "error": {"code": "invalid_credentials", "message": "Correo o contraseña incorrectos.", "details": None}
    }


def test_missing_or_bad_token_is_401(client):
    assert client.get("/api/v1/me").json()["error"]["code"] == "missing_session"
    response = client.get("/api/v1/me", headers={"Authorization": "Bearer basura"})
    assert response.status_code == 401 and response.json()["error"]["code"] == "invalid_session"


def test_bad_format_is_422_and_business_rule_is_400(client, login):
    headers = login("manager")
    response = client.post("/api/v1/users", headers=headers, json={"email": "x@mederi.pe"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert {item["field"] for item in response.json()["error"]["details"]} >= {"full_name", "role", "password"}
    response = client.post(
        "/api/v1/users", headers=headers,
        json={"email": "x@mederi.pe", "full_name": "X", "role": "manager", "password": "corta"},
    )
    assert response.status_code == 400 and response.json()["error"]["code"] == "weak_password"


def test_update_own_profile(client, login):
    headers = login("salesperson", "vende@mederi.pe")
    response = client.patch("/api/v1/me", headers=headers, json={"phone": "987654321"})
    assert response.status_code == 200 and response.json()["phone"] == "987654321"
    response = client.patch("/api/v1/me", headers=headers, json={"email": "nuevo@mederi.pe"})
    assert response.json()["email"] == "nuevo@mederi.pe" and response.json()["phone"] == "987654321"


def test_users_endpoints_are_manager_only(client, login):
    manager = login("manager")
    seller = login("salesperson")
    assert client.get("/api/v1/users", headers=seller).status_code == 403
    assert client.get("/api/v1/users", headers=seller).json()["error"]["code"] == "role_not_allowed"
    page = client.get("/api/v1/users?per_page=1", headers=manager).json()
    assert page["total"] == 2 and len(page["items"]) == 1 and page["per_page"] == 1


def test_create_update_and_deactivate_user(client, login):
    manager = login("manager")
    response = client.post(
        "/api/v1/users", headers=manager,
        json={"email": "nuevo@mederi.pe", "full_name": "Nuevo", "role": "salesperson", "password": PASSWORD,
              "salesperson_code": "002"},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]
    duplicated = client.post(
        "/api/v1/users", headers=manager,
        json={"email": "nuevo@mederi.pe", "full_name": "Otro", "role": "manager", "password": PASSWORD},
    )
    assert duplicated.status_code == 409
    unknown = client.post(
        "/api/v1/users", headers=manager,
        json={"email": "x@mederi.pe", "full_name": "X", "role": "salesperson", "password": PASSWORD, "salesperson_code": "999"},
    )
    assert unknown.status_code == 400 and unknown.json()["error"]["code"] == "unknown_salesperson"
    assert client.patch(f"/api/v1/users/{user_id}", headers=manager, json={"active": False}).json()["active"] is False
    login_again = client.post("/api/v1/sessions", json={"email": "nuevo@mederi.pe", "password": PASSWORD})
    assert login_again.status_code == 401
    assert client.patch("/api/v1/users/999", headers=manager, json={"active": True}).status_code == 404


def test_deactivated_user_token_stops_working(client, login):
    manager = login("manager")
    seller = login("salesperson")
    seller_id = client.get("/api/v1/me", headers=seller).json()["id"]
    client.patch(f"/api/v1/users/{seller_id}", headers=manager, json={"active": False})
    assert client.get("/api/v1/me", headers=seller).status_code == 401
