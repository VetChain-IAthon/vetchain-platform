"""Interfaz de data_imports: subir un CSV con encabezados, revisarlo y confirmarlo o cancelarlo."""
import pytest

from tests.defontana_sample import load_sample

SALESPEOPLE_HEADER = "codigo,nombre,ubicacion,c3,activo\n"


@pytest.fixture()
def manager(login, db):
    headers = login("manager")
    load_sample(db)
    return headers


def _upload(client, headers, source, text, name="archivo.csv"):
    return client.post("/api/v1/data-imports", headers=headers, data={"source": source},
                       files={"file": (name, text.encode("utf-8"), "text/csv")})


def test_stage_review_and_confirm(client, manager):
    csv = SALESPEOPLE_HEADER + "003,ROSA DIAZ,Lima,,1\n004,,Lima,,1\n001,OFICINA CENTRAL,La Victoria,000000,1\n"
    staged = _upload(client, manager, "salespeople", csv, "mederi-7-vendedores.csv")
    assert staged.status_code == 201
    body = staged.json()
    assert body["status"] == "staged" and body["rows_read"] == 3 and body["valid_rows"] == 2
    assert body["errors"] == [{"line": 3, "message": "Falta nombre: es obligatorio."}]  # la línea 1 son los encabezados
    preview = body["preview"]
    assert preview["columns"] == ["codigo", "nombre", "ubicacion", "activo"]
    assert [(r["line"], r["values"][0], r["status"]) for r in preview["rows"]] == [(2, "003", "new"), (3, "004", "error"), (4, "001", "update")]
    assert preview["new_rows"] == 1 and preview["updated_rows"] == 1
    # Aún no se aplica: el vendedor 003 no existe
    names = {s["code"]: s["name"] for s in client.get("/api/v1/reports/salespeople", headers=manager).json()["items"]}
    assert "003" not in names

    confirmed = client.patch(f"/api/v1/data-imports/{body['id']}", headers=manager, json={"action": "confirm"}).json()
    assert confirmed["status"] == "confirmed" and confirmed["rows_loaded"] == 2
    assert client.get(f"/api/v1/data-imports/{body['id']}", headers=manager).json()["preview"] is None
    again = client.patch(f"/api/v1/data-imports/{body['id']}", headers=manager, json={"action": "cancel"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "import_not_staged"

    sources = {s["source"]: s for s in client.get("/api/v1/data-sources", headers=manager).json()["items"]}
    assert sources["salespeople"]["rows_in_db"] == 3 and sources["salespeople"]["last_import"]["rows_loaded"] == 2
    assert sources["salespeople"]["headers"] == ["codigo", "nombre", "ubicacion", "c3", "activo"]
    assert sources["orders"]["first_date"] == "2025-01-10" and sources["orders"]["file_name"] == "mederi-2-pedidos.csv"
    listed = client.get("/api/v1/data-imports", headers=manager).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == body["id"]


def test_cancel_wrong_headers_and_roles(client, manager, login):
    staged = _upload(client, manager, "salespeople", SALESPEOPLE_HEADER + "009,NUEVO,,,1\n").json()
    cancelled = client.patch(f"/api/v1/data-imports/{staged['id']}", headers=manager, json={"action": "cancel"}).json()
    assert cancelled["status"] == "cancelled" and cancelled["rows_loaded"] is None

    wrong = _upload(client, manager, "orders", SALESPEOPLE_HEADER + "009,NUEVO,,,1\n")
    assert wrong.status_code == 400 and wrong.json()["error"]["code"] == "wrong_source"
    assert "Elige «7. Vendedores»" in wrong.json()["error"]["message"]
    unknown = _upload(client, manager, "orders", "a,b,c\n1,2,3\n")
    assert unknown.status_code == 400 and unknown.json()["error"]["code"] == "invalid_headers"
    empty = _upload(client, manager, "salespeople", SALESPEOPLE_HEADER)
    assert empty.status_code == 400 and empty.json()["error"]["code"] == "empty_file"
    # Un pedido de un cliente que no existe se rechaza por línea (misma regla que la carga inicial)
    orders = ("numero_pedido,fecha,ruc,nombre_cliente,codigo_vendedor,nombre_vendedor,codigo_canal,subtotal,descuento,igv,total,estado\n"
              "P9,2025-03-05,20999999999,X,001,OFICINA,001,10.00,0.00,1.80,11.80,T\n")
    rejected = _upload(client, manager, "orders", orders).json()
    assert rejected["valid_rows"] == 0
    assert rejected["errors"][0]["message"] == "ruc «20999999999» no existe en clientes. Carga primero el archivo de clientes o corrige el código."
    no_rows = client.patch(f"/api/v1/data-imports/{rejected['id']}", headers=manager, json={"action": "confirm"})
    assert no_rows.status_code == 400 and no_rows.json()["error"]["code"] == "no_valid_rows"
    assert client.get("/api/v1/data-sources", headers=login("salesperson")).status_code == 403


def test_restores_leading_zeros_lost_in_excel(client, manager):
    # Excel guarda 002 como 2 y 015 como 15: los códigos se reponen con su ancho fijo.
    header = ("ruc,nombre,direccion,telefono,correo,codigo_vendedor,nombre_vendedor,codigo_departamento,departamento,"
              "codigo_segmento,c10,codigo_condicion,c12,c13,activo,c15\n")
    row = "20990000013,PET NORTE,CAL. 88,,,2,ANA,15,LIMA,1,,1,0.00,0.00,1,0.00\n"
    staged = _upload(client, manager, "customers", header + row).json()
    assert staged["valid_rows"] == 1 and staged["errors"] == []
    client.patch(f"/api/v1/data-imports/{staged['id']}", headers=manager, json={"action": "confirm"})
    assert client.get("/api/v1/customers/20990000013", headers=manager).json()["salesperson_code"] == "002"
    bad_date = ("numero_pedido,fecha,ruc,nombre_cliente,codigo_vendedor,nombre_vendedor,codigo_canal,subtotal,descuento,igv,total,estado\n"
                "77,21/04/2026,20990000013,X,2,ANA,1,10.00,0.00,1.80,11.80,T\n")
    error, = _upload(client, manager, "orders", bad_date).json()["errors"]
    assert error["message"] == "Valor no válido en fecha («21/04/2026»): usa el formato AAAA-MM-DD, por ejemplo 2026-04-21."
