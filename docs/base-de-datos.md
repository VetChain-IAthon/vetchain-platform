# Base de datos

Las columnas son las **propuestas** del diseño; los CSV originales no traen encabezados.
Los nombres de tablas y columnas están en inglés; se conservan los términos peruanos `ruc`, `igv` y `kardex`.

## Tablas importadas de los CSV (solo lectura)
Definidas en `app/core/mederi_tables.py`.

| Tabla | CSV de Mederi | Filas | Columnas |
|---|---|---|---|
| customers | clientes | 1 330 | ruc (PK), name, address, phone, email, region (departamento), customer_type |
| sales_reps | vendedores | 6 | code (PK), name |
| orders | pedidos | 14 945 | id (PK), order_date, ruc (FK customers), sales_rep_code (FK sales_reps), subtotal, discount, igv, total, status |
| order_items | pedido_detalle | 67 403 | order_id (PK, FK), line (PK), product_code (FK), quantity, unit_price, discount, total |
| products | productos | 114 códigos (91 veterinarios) | code (PK), name, family |
| kardex | kardex | 9 970 | warehouse (PK), year (PK), month (PK), product_code (PK, FK), balance |
| payments | cobros | 14 082 | payment_number (PK), order_id (FK), ruc (FK), amount, payment_date |

## Tablas propias de la app
Cada una vive en el `models.py` de su módulo.

| Tabla | Módulo | Columnas |
|---|---|---|
| users | auth | id (PK), email, password_hash, role, sales_rep_code (FK), active |
| contacts | customers | id (PK), ruc (FK), user_id (FK), outcome, contact_date |
| quotes | quotes | id (PK), ruc (FK), user_id (FK), status, discount_pct, total, created_at |
| quote_lines | quotes | quote_id (PK, FK), product_code (PK, FK), quantity, unit_price |
| customer_tiers | pricing | tier (PK: A, B, C), max_discount_pct, margin_pct, credit_days |
| customer_rebates | pricing | ruc (PK, FK), rebate_pct |

## Relaciones
Un cliente tiene muchos pedidos; un pedido tiene muchas líneas de detalle y muchos cobros;
un vendedor atiende muchos pedidos; un producto aparece en muchas líneas y muchos registros de kardex.

## Pendiente de confirmar con Mederi
- `kardex.balance` es el stock del mes.
- `payments.order_id` enlaza cada cobro con su pedido.
- Valores posibles de `orders.status`.
