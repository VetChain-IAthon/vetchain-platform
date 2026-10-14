"""Interfaz de messaging: remitentes permitidos y envío de correos por Resend."""
import base64
import json

import httpx
import pytest

from app.main import app
from app.modules.messaging.infrastructure.orm import EmailSenderRow
from app.modules.messaging.infrastructure.repositories import GmailSmtpGateway, ResendGateway, RoutingEmailGateway


def test_each_user_connects_own_gmail_without_smtp_password(client, login, monkeypatch):
    """El estado OAuth es de un solo uso y el envío usa solo la conexión del usuario."""
    import base64
    from urllib.parse import parse_qs, urlparse
    from app.core.config import settings
    from app.modules.messaging.infrastructure import gmail_oauth

    manager = login("manager")
    seller = login("salesperson")
    monkeypatch.setattr(settings, "google_oauth_client_id", "client-id")
    monkeypatch.setattr(settings, "google_oauth_client_secret", "client-secret")
    monkeypatch.setattr(settings, "google_oauth_token_key", "test-key")

    class Cipher:
        def encrypt(self, value): return b"sealed:" + value
        def decrypt(self, value): return value.removeprefix(b"sealed:")

    monkeypatch.setattr(gmail_oauth, "_cipher", lambda: Cipher())
    sent = []

    class Response:
        status_code = 200
        def __init__(self, value): self.value = value
        def raise_for_status(self): pass
        def json(self): return self.value

    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, data=None, json=None, headers=None):
            if url == gmail_oauth.TOKEN_URL:
                return Response({"access_token": "access", "refresh_token": "refresh"} if data["grant_type"] == "authorization_code" else {"access_token": "access"})
            assert url == gmail_oauth.SEND_URL
            sent.append(base64.urlsafe_b64decode(json["raw"] + "==").decode(errors="replace"))
            return Response({"id": "gmail-message-id"})
        def get(self, url, headers=None):
            assert url == gmail_oauth.USERINFO_URL
            return Response({"email": "persona@gmail.com", "email_verified": True})

    monkeypatch.setattr(gmail_oauth.httpx, "Client", Client)
    start = client.get("/api/v1/gmail/connect", headers=manager, params={"return_path": "/reportes"})
    assert start.status_code == 200
    auth_url = start.json()["authorization_url"]
    query = parse_qs(urlparse(auth_url).query)
    assert "https://www.googleapis.com/auth/gmail.send" in query["scope"][0]
    assert query["code_challenge_method"] == ["S256"]
    callback = client.get("/api/v1/gmail/callback", params={"state": query["state"][0], "code": "google-code"}, follow_redirects=False)
    assert callback.status_code == 307 and callback.headers["location"].endswith("/reportes")
    assert client.get("/api/v1/gmail/callback", params={"state": query["state"][0], "code": "google-code"}).status_code == 400
    assert client.get("/api/v1/gmail/connection", headers=manager).json()["email"] == "persona@gmail.com"
    assert client.get("/api/v1/gmail/connection", headers=seller).json()["email"] is None
    body = {"sender_id": None, "to": ["cliente@ejemplo.pe"], "subject": "Resumen", "body": "Hola"}
    assert client.post("/api/v1/emails", headers=seller, json=body).status_code == 400
    response = client.post("/api/v1/emails", headers=manager, json=body)
    assert response.status_code == 201 and response.json()["from_email"] == "persona@gmail.com"
    assert "cliente@ejemplo.pe" in sent[0]
from app.modules.messaging.interface import dependencies as deps

PDF = base64.b64encode(b"%PDF-1.4 ficha").decode()


@pytest.fixture(autouse=True)
def no_real_provider():
    """Las pruebas nunca usan la clave del .env local."""
    app.dependency_overrides[deps.get_gateway] = lambda: ResendGateway("")
    yield
    app.dependency_overrides.pop(deps.get_gateway, None)


@pytest.fixture()
def resend():
    """Resend simulado: guarda la solicitud y devuelve un identificador."""
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"id": "msg-1"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    app.dependency_overrides[deps.get_gateway] = lambda: ResendGateway("re_prueba", client)
    yield sent
    app.dependency_overrides.pop(deps.get_gateway, None)


def test_senders_are_managed_by_managers(client, login):
    manager, seller = login("manager"), login("salesperson")
    first = client.post("/api/v1/email-senders", headers=manager, json={"name": "Mederi Pharma", "address": "Ventas@Mederi.pe"}).json()
    assert first["address"] == "ventas@mederi.pe" and first["is_default"] is True and first["is_domain"] is False
    domain = client.post("/api/v1/email-senders", headers=manager, json={"name": "Equipo Mederi", "address": "@mederi.pe", "is_default": True}).json()
    assert domain["is_domain"] is True
    setup = client.get("/api/v1/email-senders", headers=seller).json()
    assert [(s["address"], s["is_default"]) for s in setup["senders"]] == [("@mederi.pe", True), ("ventas@mederi.pe", False)]
    assert setup["provider_configured"] is False  # sin RESEND_API_KEY en las pruebas
    assert client.post("/api/v1/email-senders", headers=seller, json={"name": "X", "address": "x@y.pe"}).status_code == 403
    bad = client.post("/api/v1/email-senders", headers=manager, json={"name": "X", "address": "mederi.pe"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_sender_address"
    dup = client.post("/api/v1/email-senders", headers=manager, json={"name": "Otra", "address": "ventas@mederi.pe"})
    assert dup.status_code == 400 and dup.json()["error"]["code"] == "duplicate_sender"
    assert client.delete(f"/api/v1/email-senders/{first['id']}", headers=manager).status_code == 204


def test_send_with_domain_sender_and_attachment(client, login, resend):
    manager = login("manager")
    sender = client.post("/api/v1/email-senders", headers=manager, json={"name": "Mederi Pharma", "address": "@mederi.pe"}).json()
    body = {"sender_id": sender["id"], "from_email": "miguel@mederi.pe", "to": ["Compras@Cliente.pe"], "reply_to": "miguel@mederi.pe",
            "subject": "Resumen de compras", "body": "Estimados, les compartimos el resumen.",
            "attachments": [{"file_name": "ficha.pdf", "content_base64": PDF}]}
    sent = client.post("/api/v1/emails", headers=manager, json=body)
    assert sent.status_code == 201 and sent.json()["status"] == "sent" and sent.json()["to"] == ["compras@cliente.pe"]
    payload = json.loads(resend[0].read())
    assert str(resend[0].url) == "https://api.resend.com/emails"
    assert payload["from"] == "Mederi Pharma <miguel@mederi.pe>"
    assert payload["to"] == ["compras@cliente.pe"] and payload["text"] == body["body"]
    assert payload["reply_to"] == "miguel@mederi.pe" and payload["attachments"][0]["filename"] == "ficha.pdf"
    assert payload["attachments"][0]["content"] == PDF
    assert resend[0].headers["Authorization"] == "Bearer re_prueba"

    outside = client.post("/api/v1/emails", headers=manager, json={**body, "from_email": "yo@gmail.com"})
    assert outside.status_code == 400 and outside.json()["error"]["code"] == "sender_mismatch"
    bad_to = client.post("/api/v1/emails", headers=manager, json={**body, "to": ["cliente"]})
    assert bad_to.status_code == 400 and bad_to.json()["error"]["code"] == "invalid_recipient"


def test_without_api_key_the_email_is_simulated(client, login):
    manager = login("manager")
    sender = client.post("/api/v1/email-senders", headers=manager, json={"name": "Ventas", "address": "ventas@mederi.pe"}).json()
    sent = client.post("/api/v1/emails", headers=login("salesperson"), json={"sender_id": sender["id"], "to": ["a@b.pe"],
                                                                              "subject": "Hola", "body": "Prueba"})
    assert sent.status_code == 201 and sent.json()["status"] == "simulated" and sent.json()["from_email"] == "ventas@mederi.pe"


def test_resend_rejects_unverified_sender_without_recording_success(client, login):
    manager = login("manager")
    sender = client.post("/api/v1/email-senders", headers=manager, json={"name": "Ventas", "address": "ventas@mederi.pe"}).json()
    transport = httpx.MockTransport(lambda _request: httpx.Response(403, json={"name": "validation_error"}))
    provider = httpx.Client(transport=transport)
    app.dependency_overrides[deps.get_gateway] = lambda: ResendGateway("re_prueba", provider)
    try:
        response = client.post("/api/v1/emails", headers=manager, json={"sender_id": sender["id"], "to": ["a@b.pe"],
                                                                   "subject": "Hola", "body": "Prueba"})
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "sender_not_verified"
    finally:
        app.dependency_overrides.pop(deps.get_gateway, None)
        provider.close()


def test_unsupported_public_mailbox_cannot_be_sender_even_if_previously_saved(client, login, db, resend):
    manager = login("manager")
    rejected = client.post("/api/v1/email-senders", headers=manager,
                           json={"name": "Mederi Pharma", "address": "ventas@hotmail.com"})
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "sender_public_domain"

    allowed = client.post("/api/v1/email-senders", headers=manager,
                          json={"name": "Mederi Pharma", "address": "ventas@mederi.pe"}).json()
    db.get(EmailSenderRow, allowed["id"]).address = "ventas@hotmail.com"
    db.commit()
    attempt = client.post("/api/v1/emails", headers=manager,
                          json={"sender_id": allowed["id"], "to": ["cliente@gmail.com"],
                                "subject": "Prueba", "body": "Hola"})
    assert attempt.status_code == 400
    assert attempt.json()["error"]["code"] == "sender_public_domain"
    assert resend == []


def test_gmail_sender_uses_authenticated_smtp_account(client, login, monkeypatch):
    sent = []

    class FakeSmtp:
        def __init__(self, host, port, **kwargs):
            assert (host, port) == ("smtp.gmail.com", 465)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, account, password):
            assert (account, password) == ("remitente@gmail.com", "abcdefghijklmnop")

        def send_message(self, message, **kwargs):
            sent.append((message, kwargs))
            return {}

    monkeypatch.setattr("app.modules.messaging.infrastructure.repositories.smtplib.SMTP_SSL", FakeSmtp)
    app.dependency_overrides[deps.get_gateway] = lambda: RoutingEmailGateway(
        ResendGateway(""), GmailSmtpGateway("remitente@gmail.com", "abcdefghijklmnop"),
    )
    manager = login("manager")
    sender = client.post("/api/v1/email-senders", headers=manager,
                         json={"name": "Mederi Pharma", "address": "remitente@gmail.com"}).json()
    assert client.get("/api/v1/email-senders", headers=manager).json()["provider_configured"] is True
    response = client.post("/api/v1/emails", headers=manager,
                           json={"sender_id": sender["id"], "to": ["cliente@ejemplo.pe"],
                                 "subject": "Resumen", "body": "Hola", "attachments": [
                                     {"file_name": "ficha.pdf", "content_base64": PDF},
                                 ]})
    assert response.status_code == 201 and response.json()["status"] == "sent"
    message, envelope = sent[0]
    assert message["From"] == "Mederi Pharma <remitente@gmail.com>"
    assert message["Subject"] == "Resumen"
    assert envelope == {"from_addr": "remitente@gmail.com", "to_addrs": ["cliente@ejemplo.pe"]}
    assert message.get_payload()[1].get_filename() == "ficha.pdf"


def test_gmail_sender_requires_matching_credentials(client, login):
    app.dependency_overrides[deps.get_gateway] = lambda: RoutingEmailGateway(ResendGateway("re_test"), GmailSmtpGateway("", ""))
    manager = login("manager")
    sender = client.post("/api/v1/email-senders", headers=manager,
                         json={"name": "Mederi Pharma", "address": "remitente@gmail.com"}).json()
    assert client.get("/api/v1/email-senders", headers=manager).json()["provider_configured"] is False
    response = client.post("/api/v1/emails", headers=manager,
                           json={"sender_id": sender["id"], "to": ["cliente@ejemplo.pe"],
                                 "subject": "Resumen", "body": "Hola"})
    assert response.status_code == 400 and response.json()["error"]["code"] == "gmail_not_configured"
