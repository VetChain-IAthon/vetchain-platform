# Módulos: qué debe hacer cada uno

Estado: `auth` funciona (login y `/me`). Los demás tienen solo `GET /api/<modulo>/status`.

## auth
`POST /api/auth/login`, `GET /api/auth/me`. Falta: crear, listar y desactivar usuarios (solo rol `management`).

## data_import (`/api/data-import`)
Importar los 7 CSV (sin encabezados) a las tablas de `mederi_tables.py`. Validar filas, reportar errores por línea y
permitir recargar sin duplicar. Script de apoyo: `scripts/load_csv.py`.

## prediction
Cargar `models/model.json` y devolver la probabilidad de recompra por cliente. Entrenamiento en
`scripts/train_model.py`. Referencia de calidad: AUC 0.82; precisión ~84 % en el 10 % superior.

## customers
Lista de clientes dormidos ordenada por probabilidad, ficha del cliente y registro de contactos
(con resultado). El contacto por WhatsApp es solo un enlace `wa.me`, sin API.

## explanations
Pide a Gemini un texto corto que explique la alerta. Prompt en `prompts/alert_explanation.md`.
Enviar solo cifras agregadas; si no hay clave o falla la llamada, devolver un texto de reserva sin IA.

## pricing
Niveles A/B/C (descuento máximo, margen, días de crédito) y rebajas por cliente.

## quotes
Crear y listar cotizaciones. Validar el descuento contra el nivel del cliente (módulo pricing).

## reports
KPIs y reportes de ventas, clientes, stock, cobranza y vendedores. Indicar el origen del dato.

## planning
Pronóstico de demanda por producto para planificar importaciones. Si faltan datos o costos validados,
devolver un aviso y no una cantidad.
