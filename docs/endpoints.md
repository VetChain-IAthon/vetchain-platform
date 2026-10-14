# Contrato de endpoints (base `/api/v1`)

Capa de interfaz de la API. Las reglas de cada capa están en [`capas.md`](capas.md) y
[`capas-aplicacion-presentacion.md`](capas-aplicacion-presentacion.md). `tests/test_contract.py` verifica que las rutas de
la app coincidan con las tablas de este documento, y `docs/openapi.json` se regenera con `python -m scripts.export_openapi`.

- **Roles:** M = `manager` (gerencia), S = `salesperson` (vendedor).
- **Estado:** ✅ hecho · ⏳ responde 501 hasta que se construya el módulo.
- **Origen del dato:** las respuestas con cifras llevan `data_origin` (`real` | `synthetic` | `estimated` | `simulated`).

## Convenciones REST
- Sustantivos en plural y sin verbos en la ruta: `/customers`, no `/getCustomers`. Minúsculas con guiones: `/quotation-previews`.
- Filtros, orden y paginación en la URL: `?status=dormant&sort=-sales_12m&page=1&per_page=20`.
- Métodos: GET lee, POST crea, PUT reemplaza, PATCH cambia una parte, DELETE elimina.
- Códigos: 200 ok, 201 creado, 204 sin contenido, 400 regla de negocio rota, 401 sin sesión, 403 sin permiso,
  404 no existe, 409 conflicto de estado, 422 formato inválido, 501 aún no construido.
- Una sola forma de error: `{"error": {"code": "...", "message": "...", "details": ...}}`. `message` va en español.
- Listas: `{"items": [...], "total", "page", "per_page"}`.
- Dinero como número en soles (PEN), sin IGV salvo que el campo diga `_with_tax`. Fechas ISO. Sin PDF: el formato
  visual y los PDF los hace la web.
- Autenticación: `Authorization: Bearer <token>` en todo, salvo `POST /sessions` y `GET /health`.
- Alcance del vendedor: para un `salesperson` el backend fuerza el filtro `salesperson_code` con su propio código,
  sin importar lo que mande la web.

## Sesión y perfil — `auth`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| POST | /sessions | Iniciar sesión; devuelve el token y el usuario | todos | ✅ |
| GET | /me | Usuario actual y su rol (la web arma el menú) | M, S | ✅ |
| PATCH | /me | Cambiar el correo o el teléfono propios | M, S | ✅ |

## Usuarios — `auth`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /users | Listar usuarios | M | ✅ |
| POST | /users | Crear un usuario | M | ✅ |
| PATCH | /users/{user_id} | Cambiar el rol o activar / desactivar | M | ✅ |

## Alertas — `customers`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /alerts | Alertas del día, ordenadas por dinero en juego. Filtros: date, salesperson_code, contacted | M, S | ⏳ |
| GET | /alerts/summary | Totales: alertas, contactados hoy, monto de 12 meses en juego | M, S | ⏳ |
| GET | /alerts/{alert_id} | Una alerta: producto habitual, producto cruzado, motivos y probabilidad | M, S | ⏳ |
| GET | /alerts/{alert_id}/explanation | Texto de IA (Gemini, solo cifras agregadas) | M, S | ⏳ |

## Clientes — `customers`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /customers | Lista por monto de 12 meses. Filtros: level, search, salesperson_code (status llega con las alertas) | M, S | ✅ |
| GET | /customers/{ruc} | Ficha con nivel y resumen de 12 meses | M, S | ✅ |
| GET | /customers/{ruc}/orders | Historial de pedidos | M, S | ✅ |
| GET | /customers/{ruc}/products | Qué compra y con qué frecuencia | M, S | ✅ |
| GET | /customers/{ruc}/commercial-terms | Nivel, margen, descuento máximo y días de crédito | M, S | ✅ |
| GET | /customers/{ruc}/contacts | Registro de contactos | M, S | ✅ |
| POST | /customers/{ruc}/contacts | Registrar un contacto y su resultado | M, S | ✅ |
| GET | /customers/{ruc}/whatsapp-link | Enlace wa.me con el mensaje sugerido | M, S | ✅ |
| GET | /customers/{ruc}/brief | Ficha para reunión. Query: from, to, projection (month, semester, year) | M | ⏳ |

Fecha de corte: la ventana de 12 meses termina en el último pedido cargado (`data_as_of`), no en la fecha de hoy,
porque los CSV son una foto. `level` es `null` (y `levels_configured` es `false`) mientras gerencia no defina los
umbrales; filtrar por nivel o pedir `commercial-terms` sin umbrales responde 400 `thresholds_not_configured`.
Un vendedor solo ve su cartera: pedir un cliente ajeno responde 403 `outside_portfolio`.

## Productos y cotizaciones — `quotations`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /products | Buscar productos veterinarios activos. Filtros: search, family; paginado | M, S | ✅ |
| GET | /products/{code} | Un producto con su último precio pagado sin IGV (estimated; null si falta) | M, S | ✅ |
| POST | /quotation-previews | Calcular totales, IGV y margen sin guardar; exige reglas en Ajustes | M, S | ✅ |
| GET | /quotations | Lista paginada. Filtros: status, ruc, from, to; cartera forzada para S | M, S | ✅ |
| POST | /quotations | Emitir. Si requiere aprobación, solo un M puede confirmarla (`approval_confirmed` y nota) | M, S | ✅ |
| GET | /quotations/{quotation_id} | Detalle con líneas, limitado a la cartera para S | M, S | ✅ |

Solo se cotizan productos veterinarios activos con un precio pagado no bonificado en un pedido no cancelado.
El precio de referencia es el importe de la última línea dividido entre su cantidad y lleva origen `estimated`.
Sin precio, la vista previa responde `reference_price_unavailable`; sin costos, `margin_pct=null` y aviso `no_cost_data`.
La emisión recalcula la vista previa, no confía en importes enviados por la web. Las cotizaciones emitidas son inmutables.

## Predicción — `prediction`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /prediction/model | Versión, fecha de entrenamiento, AUC y precisión en el 10 % superior | M | ⏳ |

## Panel y reportes — `reports`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /dashboard/summary | Resumen semanal y cifras principales (incluye pedidos por mes y seguimiento de alertas) | M | ⏳ |
| GET | /reports | Catálogo de reportes con el origen de sus datos | M | ⏳ |
| GET | /reports/kpis | Los KPIs con su estado | M | ⏳ |
| GET | /reports/sales | Pedidos por mes, producto y categoría; precio pagado frente a referencia | M | ⏳ |
| GET | /reports/customers | Concentración, maestro de clientes, en riesgo y dormidos | M | ⏳ |
| GET | /reports/stock | Estado del stock, sobrestock y quiebres | M | ⏳ |
| GET | /reports/receivables | Deuda por antigüedad y nivel (estimada) | M | ⏳ |
| GET | /reports/salespeople | Pedidos de 12 meses y seguimiento de alertas por vendedor | M | ⏳ |
| GET | /reports/funnel | Embudo: alertas, contactos, cotizaciones, convertidas y monto recuperado | M | ⏳ |

Todos aceptan `?from=&to=`.

## Preguntas a los datos — `explanations`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| POST | /insights/questions | Pregunta en lenguaje natural; la respuesta sale de la base y lista sus fuentes | M | ⏳ |

## Planificación de importación — `import_planning`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /import-suggestions | Pedido sugerido por producto. Filtro: supplier | M | ⏳ |
| PATCH | /import-suggestions/{suggestion_id} | Decisión: approved, rejected o volver a pending | M | ⏳ |

Sin stock y costos validados, la respuesta lleva un aviso y solo la demanda mensual es real.

## Ajustes — `settings`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /settings/pricing | IGV, días de vigencia, margen mínimo, rebaja de margen en promociones | M | ✅ |
| PUT | /settings/pricing | Cambiar esos valores | M | ✅ |
| GET | /settings/customer-levels | Niveles A, B y C con margen, descuento máximo y días de crédito | M, S | ✅ |
| PUT | /settings/customer-levels/{level} | Cambiar un nivel | M | ✅ |
| GET | /settings/level-thresholds | Montos de 12 meses para ser B y A | M | ✅ |
| PUT | /settings/level-thresholds | Cambiar los umbrales | M | ✅ |

Mientras gerencia no configure un valor, el GET responde 404 (`pricing_not_configured`, `thresholds_not_configured`),
y `customer-levels` devuelve `missing_levels`. No hay valores por defecto inventados.

## Carga de datos — `data_imports`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /data-sources | Los 7 archivos: contenido, registros, período y estado | M | ⏳ |
| POST | /data-imports | Subir un CSV (multipart, campo `source`); se valida, no se aplica | M | ⏳ |
| GET | /data-imports | Cargas anteriores | M | ⏳ |
| GET | /data-imports/{import_id} | Revisión: filas leídas y errores por línea | M | ⏳ |
| PATCH | /data-imports/{import_id} | Confirmar (actualiza e inserta, nunca borra) o cancelar | M | ⏳ |

## General
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /health | La API está viva (fuera de `/api/v1`) | todos | ✅ |

## Cambios respecto a la primera versión del contrato
Prevalecen el contrato de capas y la tabla de casos de uso:
- **Sin PDF en el backend.** Se quitaron `/customer-briefs/{id}/pdf`, `/quotations/{id}/pdf` y "agregar /pdf a cualquier reporte".
- **Ficha para reunión.** `POST /customer-briefs` y `GET /customer-briefs/{id}` pasan a `GET /customers/{ruc}/brief`
  (caso de uso `GetCustomerBrief`), porque no se guarda.
- **Cotizaciones.** Una cotización emitida no se edita: se quitaron `PUT` y `PATCH /quotations/{id}`. Los estados son
  `issued`, `converted` y `expired`; la conversión y el vencimiento los calcula `MatchConversions` al cargar pedidos.
  La aprobación se confirma al emitir.
- **Cerrar sesión.** Se quitó `DELETE /sessions/current`: con JWT sin lista de revocados, cerrar sesión es borrar el
  token en la web.
- **Panel.** `/dashboard/monthly-sales` y `/dashboard/alert-follow-up` se integran en `/dashboard/summary` y
  `/reports/salespeople`. `/reports/overview` se reemplaza por `/reports/funnel`.
- **Nuevo:** `GET /prediction/model`.
