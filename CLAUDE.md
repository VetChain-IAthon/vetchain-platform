# VetChain · Backend

API de VetChain, plataforma de inteligencia comercial para Mederi (importadora veterinaria, Perú).
Ayuda a gerencia, compras y administración a decidir con datos. El frontend vive en otro repositorio.

## Stack
- FastAPI (Python 3.11+), SQLAlchemy 2.0, PostgreSQL en Neon (SQLite en local)
- Modelo de predicción: XGBoost, archivo `models/model.json` dentro del repo
- IA generativa: Gemini API (capa gratuita). Solo se le envían cifras agregadas, nunca nombres de clientes ni RUC.
- Despliegue: Render publica solo al subir a `main`. No hay GitHub Actions por ahora.

## Arquitectura: monolito modular
Una sola API. Cada módulo es una carpeta en `app/modules/` con sus archivos:
`router.py` (rutas), `service.py` (lógica), `schemas.py` (datos de entrada y salida), `models.py` (tablas propias).

Reglas:
1. Un módulo **no importa el `models.py` de otro**. Si necesita sus datos, llama al `service.py` de ese módulo.
2. Las tablas de los CSV de Mederi (solo lectura) viven en `app/core/mederi_tables.py` y las puede leer cualquier módulo.
3. Lo compartido (configuración, base de datos, seguridad) va en `app/core/`. Nada de lógica de negocio ahí.
4. Para agregar un módulo: crea la carpeta, y regístralo en `app/modules/__init__.py`.

Módulos y dependencias permitidas:
- `auth` (usuarios y sesión)
- `customers` (alertas de clientes dormidos, contactos) → usa `prediction` y `explanations`
- `explanations` (texto con Gemini)
- `pricing` (niveles y reglas de descuento)
- `quotes` (cotizaciones) → usa `pricing`
- `prediction` (modelo XGBoost)
- `reports` (KPIs y reportes de ventas, clientes, stock, cobranza, vendedores)
- `planning` (planificación de importación) → usa `prediction`
- `data_import` (importar los CSV de Mederi; ruta `/api/data-import`)

## Datos
Siete CSV de Mederi **sin encabezados**: clientes (1 330), pedidos (14 945), pedido_detalle (67 403),
productos (114 códigos, 91 veterinarios), kardex (9 970), cobros (14 082), vendedores (6).
En la base se llaman `customers`, `orders`, `order_items`, `products`, `kardex`, `payments`, `sales_reps`.
Los nombres de columnas en `mederi_tables.py` son **propuestos**. Pendiente confirmar con Mederi:
- `kardex.balance` = stock mensual
- `payments` (cobros) se enlazan por `order_id`
Más en `docs/base-de-datos.md`.

## Reglas de producto
- Un pedido no es una venta facturada: cuidar nombres y textos.
- Los datos que se devuelven indican su origen cuando aplica: `real`, `synthetic`, `estimated` o `simulated`.
- No devolver cantidades de importación ni rentabilidad como confiables si faltan datos o costos: devolver un aviso.
- Montos en soles (PEN). Guardar con `Numeric(12, 2)`.
- Roles: solo dos, `management` (gerencia) y `sales_rep` (vendedor).

## Convenciones
- Código en inglés: variables, funciones, clases, archivos, módulos, tablas, columnas, rutas, claves JSON y valores internos (roles, estados).
  Se conservan los términos peruanos `ruc`, `igv` y `kardex`.
- En español: mensajes al usuario, mensajes de error y documentación (docstrings, comentarios, `docs/`, prompts de Gemini).
- Rutas en inglés bajo `/api/<module>/...`, con guiones si son varias palabras. Cada módulo tiene `GET /api/<module>/status`.
- Secretos solo en variables de entorno (ver `.env.example`).
- Un módulo por vez, con pruebas en `tests/`.

## Comandos
- Instalar: `pip install -r requirements.txt`
- Crear tablas: `python -m scripts.create_tables`
- Correr: `uvicorn app.main:app --reload`
- Probar: `pytest`

## Qué falta (en este orden sugerido)
1. `data_import`: leer los 7 CSV y cargarlos en las tablas de `mederi_tables.py`.
2. `auth`: ya funciona login y `/me`; falta crear usuarios desde un administrador.
3. `prediction`: entrenar y cargar el modelo (`scripts/train_model.py`).
4. `customers`, `explanations`, `pricing`, `quotes`, `reports`, `planning`.
5. Cambiar `create_all` por migraciones (Alembic) antes de producción.
