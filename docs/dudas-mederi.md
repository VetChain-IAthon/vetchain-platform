# Dudas para Mederi

Columnas y reglas que hay que confirmar con Mederi. En el código, las columnas dudosas llevan el comentario
`POR CONFIRMAR` en `app/infrastructure/db/source_models.py`. Cambiar un nombre es un cambio de una línea en el ORM
y en el parser (`app/infrastructure/loaders/defontana_csv.py`); después hay que regenerar el DDL
(`python -m scripts.export_ddl`).

## Columnas por confirmar

| Tabla | Columna | CSV | Qué creemos que es | Valores vistos |
|---|---|---|---|---|
| customers | segment_code | 1_clientes c9 | Segmento o tipo de cliente | 6 códigos (001, 004, 006, 008…) |
| customers | condition_code | 1_clientes c11 | Condición de pago (contado / crédito) | 001, 002; 5 vacíos |
| products | category_code | 4_productos c3 | Categoría o familia | 8 códigos |
| products | unit_code | 4_productos c5 | Unidad de medida | 5 códigos |
| orders | channel_code | 2_pedidos c6 | Canal o tipo de pedido | 001, 002 |
| order_lines | unit_code | 3_detalle c7 | Unidad de medida de la línea | 8 códigos |
| order_lines | quantity_dispatched | 3_detalle c9 | Cantidad despachada. c10 es casi igual (difiere en 54 líneas) y no se guarda | |
| stock_balances | balance | 5_kardex c5 | Saldo al cierre del mes (no el movimiento del mes) | 22 saldos negativos |
| receipts | type_code | 6_cobros c4 | Tipo de documento cobrado | 001, 002, 005 |
| receipts | code_c6 | 6_cobros c6 | Desconocido | 001, 002 |
| receipts | payment_method_code | 6_cobros c7 | Medio de pago | 11 códigos |
| receipts | code_c8 | 6_cobros c8 | Desconocido (¿banco?) | 5 códigos |
| receipts | applied_date | 6_cobros c11 | Fecha de aplicación del cobro | Casi siempre igual a la fecha del cobro |

## Estados del pedido (`orders.status_code`)

Confirmado por el equipo: T = En tránsito, A = Almacén / Aprobado, C = Cancelado, D = Devuelto / Entregado,
vacío = sin dato (14 pedidos).

- **T es el 92 % de los pedidos** (13 846 de 14 945), así que probablemente incluye pedidos ya entregados.
- ¿D es "devuelto" o "entregado"? Cambia si cuenta como venta.
- Hoy las consultas excluyen solo los cancelados (C) de las compras. ¿Cuáles cuentan como "venta"?

## Otras dudas

1. **Clientes sin RUC de 11 dígitos.** 18 de los 1 330 tienen otro largo: 12 de 8 dígitos (¿DNI?), 3 de 9, 2 de 10
   y 1 de 14. Pesan el 0,47 % del monto, pero los 12 de 8 dígitos están activos (245 pedidos, el último en enero de 2026).
   **Decisión tomada:** se cargan con `tax_id_kind = other` y el dominio (`Ruc`) acepta de 8 a 15 dígitos, con `kind`
   para distinguirlos. Falta confirmar con Mederi si los de 9, 10 y 14 dígitos son errores de digitación.
2. **Cobros y pedidos.** El CSV de cobros trae número de comprobante (c5), no de pedido, así que `receipts` no se
   enlaza con `orders`. Sin embargo, c0 coincide con un número de pedido en 7 844 de los 14 082 cobros: ¿es casualidad
   de numeración o es el pedido? Para cuentas por cobrar hace falta el CSV de comprobantes con número de pedido.
3. **Kardex fuera de catálogo.** 5 códigos del kardex no están en productos: I0MT000001, I0MT000005, I0MT000006,
   SRV0000001, TCM0000013.
4. **Líneas repetidas.** 18 pares (pedido, línea) aparecen dos veces con datos distintos. Se conservan ambas con
   `dup_seq` 0 y 1. ¿Son líneas reales o un error de exportación?
5. **Bonificaciones.** El 29 % de las líneas tiene precio simbólico (≤ 0.01). Se marcan `is_bonus` y no suman en
   montos ni en el precio de referencia. ¿Es correcto?
6. **Productos no veterinarios.** 24 de los 115 productos no empiezan con MED (camas, autos, eventos, mantas, paños,
   revistas…) y aparecen en 1 212 líneas. Se excluyen de las métricas.
7. **Costos.** Ningún CSV trae costo ni precio de lista: el margen sale nulo con aviso `no_cost_data`.
