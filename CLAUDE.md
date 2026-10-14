# VetChain · Backend

API de VetChain, plataforma de inteligencia comercial para Mederi (importadora veterinaria, Perú).
Ayuda a gerencia y a los vendedores a decidir con datos. El frontend vive en otro repositorio.

## Stack
- FastAPI (Python 3.11+), SQLAlchemy 2.0, PostgreSQL en Neon (SQLite en local)
- Modelo de predicción: XGBoost, archivo `models/model.json` dentro del repo
- IA generativa: Gemini API (capa gratuita). Solo se le envían cifras agregadas, nunca nombres de clientes ni RUC.
- Despliegue: Render publica solo al subir a `main`. No hay GitHub Actions por ahora.

## Arquitectura: monolito modular por capas
Una sola API. **El contrato está en `docs/capas.md`: leerlo antes de construir un módulo.** Resumen:

- Cada módulo en `app/modules/<module>/` tiene cuatro capas: `domain/` (entidades, objetos de valor, reglas, puertos
  como `Protocol`), `application/` (casos de uso con `execute`, y `public.py`), `infrastructure/` (ORM con sufijo `Row`,
  repositorios, Gemini, XGBoost, CSV) e `interface/` (router, esquemas Pydantic `In`/`Out`, `dependencies.py` para el cableado).
- Las dependencias apuntan al dominio: `interface → application → domain ← infrastructure`. domain y application no
  importan FastAPI, SQLAlchemy, Pydantic ni infrastructure.
- Entre módulos solo se llama a `application/public.py` del otro, a través de un puerto `<Módulo>Gateway` propio.
  Nunca se importa el domain, la infrastructure ni el ORM de otro módulo.
- Las tablas de los CSV las escribe solo `data_imports` (upsert, nunca borra). Los demás módulos las leen con repositorios propios.
- El dominio lanza `BusinessRuleError`, `NotFoundError`, `ForbiddenError` o `ConflictError`, y la interfaz los traduce
  a 400, 404, 403 y 409 (`app/core/errors.py`).
- El shared_kernel va en `app/core/`: `Money`, `Percentage`, `Ruc`, `DataOrigin`, `DateRange`, `Clock`, `UnitOfWork`, `Page[T]`.
- Sin PDF en el backend: dinero como número y fechas ISO.
- `tests/test_architecture.py` verifica estas reglas.

Módulos y a quién pueden llamar:
- `auth`, `settings`, `prediction`: a ninguno
- `customers` → prediction, explanations, settings
- `quotations` → settings, customers
- `import_planning` → prediction
- `data_imports` → quotations
- `reports` → settings, data_imports
- `explanations` → reports

**Estado del código:** sigue en estructura plana (`router.py`, `service.py`, `schemas.py`, `models.py`) y con nombres
anteriores (`pricing`, `quotes`, `planning`, `data_import`, roles `management`/`sales_rep`, tablas `sales_reps`,
`order_items`, `kardex`). Cada módulo se pasa a capas y se renombra cuando se construye (ver `docs/capas.md`, sección 8).
Hay puntos abiertos en la sección 9 de `docs/capas.md`, entre ellos un ciclo de dependencias.

## Datos
Siete CSV de Mederi **sin encabezados**: clientes (1 330), pedidos (14 945), pedido_detalle (67 403),
productos (114 códigos, 91 veterinarios), kardex (9 970), cobros (14 082), vendedores (6).
En la base se llaman `customers`, `orders`, `order_lines`, `products`, `stock_balances`, `payments` y `salespeople`.
Los nombres de columnas son **propuestos**. Pendiente confirmar con Mederi:
- `stock_balances.balance` = stock mensual
- `payments` (cobros) se enlazan por `order_id`
- qué estados de `orders.status` cuentan como venta
Más en `docs/base-de-datos.md`.

## Reglas de producto
- Un pedido no es una venta facturada: cuidar nombres y textos.
- Los datos que se devuelven indican su origen cuando aplica: `real`, `synthetic`, `estimated` o `simulated`.
- No devolver cantidades de importación ni rentabilidad como confiables si faltan datos o costos: devolver un aviso.
- Montos en soles (PEN). Guardar con `Numeric(12, 2)`.
- Roles: solo dos, `manager` (gerencia) y `salesperson` (vendedor). El vendedor solo opera sobre su cartera.

## Convenciones
- Código en inglés: variables, funciones, clases, archivos, módulos, tablas, columnas, rutas, claves JSON y valores internos (roles, estados).
  Se conservan los términos peruanos `ruc` e `igv`.
- En español: mensajes al usuario, mensajes de error y documentación (docstrings, comentarios, `docs/`, prompts de Gemini).
- Rutas REST en inglés bajo `/api/v1/<recurso>`: sustantivos en plural, minúsculas con guiones. Además existe `/health`.
- Error con la misma forma en todas las rutas: `{"error": {"code": "...", "message": "..."}}`. Listas como `Page`: `items`, `total`, `page`, `per_page`.
- Secretos solo en variables de entorno (ver `.env.example`).
- Un módulo por vez, con pruebas por capa en `tests/` (ver `docs/capas.md`, sección 6).

## Comandos
- Instalar: `pip install -r requirements.txt`
- Crear tablas: `python -m scripts.create_tables`
- Correr: `uvicorn app.main:app --reload`
- Probar: `pytest`

## Qué falta (en este orden sugerido)
1. Resolver los puntos abiertos de `docs/capas.md` (sección 9) y guardar el contrato de endpoints en `docs/endpoints.md`.
2. Bases compartidas: `app/core/errors.py`, shared_kernel, prefijo `/api/v1`, `tests/test_architecture.py`.
3. `auth` en capas: sesiones, `/me` y `/users`, con los roles `manager`/`salesperson`.
4. `data_imports`: validar, revisar y confirmar los 7 CSV.
5. `settings`, `prediction` (`scripts/train_model.py`), `customers`, `explanations`, `quotations`, `reports`, `import_planning`.
6. Cambiar `create_all` por migraciones (Alembic) antes de producción.
