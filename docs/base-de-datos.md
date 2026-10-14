# Base de datos

Las columnas de las tablas de los CSV son **propuestas**: los CSV originales no traen encabezados.
Los nombres siguen [`capas.md`](capas.md). El código todavía usa algunos nombres anteriores (ver su sección 8).
Se conservan los términos peruanos `ruc` e `igv`.

## Tablas de los CSV (solo las escribe data_imports)
Definidas en `app/core/source_tables.py` (hoy `mederi_tables.py`). Los demás módulos solo las leen.

| Tabla | CSV de Mederi | Filas | Columnas |
|---|---|---|---|
| customers | clientes | 1 330 | ruc (PK), name, address, phone, email, region (departamento), customer_type |
| salespeople | vendedores | 6 | code (PK), name |
| products | productos | 114 códigos (91 veterinarios) | code (PK), name, family |
| orders | pedidos | 14 945 | id (PK), order_date, ruc (FK customers), salesperson_code (FK salespeople), subtotal, discount, igv, total, status |
| order_lines | pedido_detalle | 67 403 | order_id (PK, FK), line (PK), product_code (FK), quantity, unit_price, discount, total |
| stock_balances | kardex | 9 970 | warehouse (PK), year (PK), month (PK), product_code (PK, FK), balance |
| payments | cobros | 14 082 | payment_number (PK), order_id (FK), ruc (FK), amount, payment_date |

## Tablas propias de la app
Cada una vive en el `infrastructure/orm.py` de su módulo.

| Tabla | Módulo | Contenido |
|---|---|---|
| users | auth | id, email (único), password_hash, full_name, phone, role, salesperson_code (FK), active |
| alerts | customers | Una por cliente y día: ruc, fecha, probabilidad, dinero en juego, motivos, producto habitual, producto cruzado |
| contacts | customers | ruc, usuario, alerta (opcional), resultado, fecha |
| pricing_settings | settings | Tasa de IGV, días de vigencia, margen mínimo, rebaja en promociones |
| customer_levels | settings | level (PK: A, B, C), max_discount_pct, margin_pct, credit_days |
| level_thresholds | settings | Monto mínimo de 12 meses para B y para A |
| quotations | quotations | ruc, usuario, estado (issued/converted/expired), aprobación, valid_until, order_id, totales |
| quotation_lines | quotations | Producto, cantidad, precio de referencia y su origen |
| import_suggestions | import_planning | Producto, proveedor (opcional), cantidad sugerida, pedir antes de, decisión, data_origin |
| data_imports | data_imports | Fuente, origen, estado (staged/confirmed/cancelled), filas leídas, filas con error, fechas |

## Relaciones
Un cliente tiene muchos pedidos, alertas, contactos y cotizaciones. Un pedido tiene muchas líneas y muchos cobros.
Un vendedor atiende muchos pedidos. Un producto aparece en muchas líneas, en el stock mensual y en las cotizaciones.
Una cotización puede terminar enlazada a un pedido (`order_id`) cuando se convierte.

## Pendiente de confirmar con Mederi
- `stock_balances.balance` (el saldo del kardex) es el stock del mes.
- `payments.order_id` enlaza cada cobro con su pedido.
- Valores posibles de `orders.status` y cuáles cuentan como venta (el contrato menciona A, C y D).
- No hay costos, precio de lista ni proveedor por producto en los CSV.
