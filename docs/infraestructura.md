# Capa de infraestructura de base de datos

Cubre la conexión, el ORM, las consultas y la carga de los 7 CSV de Defontana. Léela junto con
[`base-de-datos.md`](base-de-datos.md) (modelo, mapa CSV → columna y política de vacíos) y
[`dudas-mederi.md`](dudas-mederi.md) (columnas por confirmar).

## 1. Qué hay hecho y qué falta

| Pieza | Archivo | Estado |
|---|---|---|
| Motor y sesión (Neon/PostgreSQL; SQLite en pruebas) | `app/core/database.py` | Hecho |
| Unidad de trabajo | `app/infrastructure/db/unit_of_work.py` | Hecho |
| ORM de las 7 tablas de Defontana | `app/infrastructure/db/source_models.py` | Hecho |
| Consultas de lectura | `app/infrastructure/db/repositories/queries.py` | Hecho (8 consultas) |
| Cargador de CSV con política de vacíos | `app/infrastructure/loaders/defontana_csv.py` | Hecho |
| Script de carga | `python -m scripts.load_csv` (lee `data/`) | Hecho |
| DDL de PostgreSQL | `docs/schema.postgres.sql` (`python -m scripts.export_ddl`) | Hecho, probado en PostgreSQL 18 |
| Migraciones Alembic | `alembic/`, migración inicial `e811b35b030d` | Hecho. El esquema migrado es idéntico al DDL (comparado con `pg_dump`) |
| Repositorios de customers | `app/modules/customers/infrastructure/repositories.py` | Hecho (`CustomerReadRepository`) |
| Repositorios de reports | `app/modules/reports/infrastructure/repositories.py` | Hecho (ventas por mes, por categoría, por cliente, stock) |
| Repositorios del resto de módulos | `app/modules/*/infrastructure/` | Falta |
| Pruebas | `tests/test_infrastructure_db.py`, `test_module_repositories.py`, `test_migrations.py`, `test_postgres_integration.py` | Hecho. La de datos reales corre si los CSV están en `data/`; la de PostgreSQL, si existe `POSTGRES_TEST_URL` |
| Base local | PostgreSQL `VetChainDb` en localhost:5432 | Migrada y cargada. Evidencia en `docs/evidencia/carga-local-2026-10-13.txt` |

## 2. Reglas de la capa
- El dominio y la aplicación no importan SQLAlchemy ni `source_models.py`. Solo la infraestructura los usa
  (lo verifica `tests/test_architecture.py`).
- Los repositorios devuelven datos simples (dict, dataclass, tipos del dominio), no entidades ORM.
- Una transacción por caso de uso, con `SqlAlchemyUnitOfWork`.
- Un módulo no lee las tablas de otro módulo. Las tablas de Defontana son de solo lectura para todos los módulos.
- `app/core/source_tables.py` es solo un re-export para compatibilidad. El código nuevo importa de
  `app.infrastructure.db.source_models`.
- El código nuevo de acceso a datos debe funcionar en PostgreSQL y en SQLite.

## 3. Cómo precargar los datos
1. Copiar los 7 CSV a `data/` con sus nombres oficiales: `mederi-1-ventas.csv` (clientes), `mederi-2-pedidos.csv`,
   `mederi-3-pedidos-detalles.csv`, `mederi-4-productos.csv`, `mederi-5-kardex.csv`, `mederi-6-cobros.csv` y
   `mederi-7-vendedores.csv`. Cada archivo se ubica por su número; también se acepta el estilo `1_clientes.csv`.
   La carpeta `data/` está en `.gitignore`, porque son datos reales de clientes.
2. Definir `DATABASE_URL` en `.env`. Local: `postgresql://far14z:<clave>@localhost:5432/VetChainDb`. En Neon:
   `postgresql://...`. El código lo convierte a `postgresql+psycopg://`.
3. Ejecutar `alembic upgrade head` para crear o actualizar las tablas.
4. Ejecutar `python -m scripts.load_csv` (o `python -m scripts.load_csv <carpeta>`). Carga en orden de dependencias y
   muestra el reporte de rechazos y avisos. Termina con código 1 si hubo filas rechazadas.
5. Se puede repetir sin problema: no duplica ni borra.

Conteos esperados: 6 vendedores, 1 330 clientes, 115 productos, 14 945 pedidos, 67 403 líneas, 9 970 saldos de kardex
y 14 082 cobros. La carga completa tarda unos 7 s en SQLite.

## 4. Consultas disponibles (`repositories/queries.py`)

| Función | Para qué |
|---|---|
| `last_order_per_customer` | Última compra, cantidad de pedidos y monto por cliente (base de las alertas) |
| `customer_orders` | Pedidos de un cliente, con filtro de fechas y paginación |
| `customer_products` | Productos que compra un cliente (solo veterinarios; el monto excluye las bonificadas) |
| `last_paid_price` | Último precio pagado de un producto: `unit_price × (1 − discount_pct/100)`. Es `estimated` y no es un costo |
| `monthly_sales` | Pedidos por mes, con monto y monto despachado (estado T) |
| `stock_at` | Stock al cierre de un mes, sumando almacenes. Toma el último saldo de cada almacén hasta ese mes, porque el kardex solo tiene fila en los meses con datos |
| `receipts_by_customer` | Cobros de un cliente |
| `products_missing_from_catalog` | Control de calidad: códigos del kardex que no están en productos |
| `customer_activity` | Monto, cantidad de pedidos y fechas con pedido por cliente desde una fecha (ritmo de compra) |
| `sales_by_category` | Monto por categoría de producto (`category_code`, POR CONFIRMAR) |
| `amounts_by_customer` | Monto por cliente, de mayor a menor (concentración de clientes) |

Reglas incorporadas:
- Un pedido no es una venta facturada.
- Los montos son sin IGV y salen de `line_total`.
- Solo cuentan los productos veterinarios.
- Los estados en `exclude_statuses` no cuentan como compra. Por defecto es `("C",)`, igual que `SalesDefinition` del dominio.
- El precio de referencia usa solo líneas no bonificadas.

## 5. Migraciones
- La configuración está en `alembic.ini` y `alembic/env.py`. Usa el motor de `app/core/database.py` y las tablas de
  `app/db_models.py`. La URL sale de `DATABASE_URL`.
- Después de cambiar el ORM: `alembic revision --autogenerate -m "..."`, revisar el archivo generado y luego
  `alembic upgrade head`. Hay que regenerar también el DDL con `python -m scripts.export_ddl`.
- `tests/test_migrations.py` falla si el ORM tiene cambios sin migración (`alembic check`).
- `scripts/create_tables.py` queda solo para pruebas.

## 6. Siguientes tareas, en orden
1. Capas de aplicación e interfaz de customers y reports sobre los repositorios que ya existen. Todavía no hay
   endpoints: hacen falta `docs/endpoints.md`, `app/core/errors.py` y el prefijo `/api/v1`.
2. Repositorios del resto de módulos.
3. Cuando Mederi responda las dudas, renombrar las columnas "POR CONFIRMAR" en el ORM, el parser y
   `data_imports/domain/sources.py`, crear la migración y regenerar el DDL.
4. Cuando exista el CSV de comprobantes con número de pedido, añadir la FK `receipts → orders` y las cuentas por cobrar.
5. Producción: proyecto en Neon (misma región que Render), `DATABASE_URL` en Render, `alembic upgrade head` y carga de los CSV.
