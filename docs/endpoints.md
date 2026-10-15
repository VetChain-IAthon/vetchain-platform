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
| GET | /customers/at-risk | En riesgo: pasaron más de 1,5 veces su ritmo de compra sin pedir (factores provisionales), por dinero en juego | M, S | ✅ |
| GET | /customers/at-risk/follow-up | Por vendedor: clientes en riesgo y soles en juego según el último contacto (o sin contactar) | M, S | ✅ |
| GET | /customers/dormant | Sin pedidos en 12 meses (incluye a los que nunca pidieron), por monto histórico. Filtros: search, customer_type, salesperson_code | M, S | ✅ |
| GET | /customers/discarded | Dormidos descartados, del más reciente al más antiguo, con motivo, nota y quién descartó. Filtros: search, reason, salesperson_code | M, S | ✅ |
| GET | /customers/{ruc} | Ficha con nivel y resumen de 12 meses | M, S | ✅ |
| GET | /customers/{ruc}/orders | Historial de pedidos | M, S | ✅ |
| GET | /customers/{ruc}/products | Qué compra y con qué frecuencia | M, S | ✅ |
| GET | /customers/{ruc}/commercial-terms | Nivel, margen, descuento máximo y días de crédito | M, S | ✅ |
| GET | /customers/{ruc}/contacts | Registro de contactos | M, S | ✅ |
| POST | /customers/{ruc}/contacts | Registrar un contacto y su resultado | M, S | ✅ |
| POST | /customers/{ruc}/discard | Descartar un cliente dormido. Motivo: business_closed, data_changed, not_viable u other (exige nota) | M | ✅ |
| DELETE | /customers/{ruc}/discard | Restaurarlo: vuelve a la lista de dormidos; el descarte queda en el historial | M | ✅ |
| GET | /customers/{ruc}/whatsapp-link | Enlace wa.me con el mensaje sugerido | M, S | ✅ |
| GET | /customers/{ruc}/brief | Ficha para reunión (interna). Query: from, to, projection (month, semester, year). Proyección, ganancia, ofertas, guion y cobranza van como avisos | M | ✅ |

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
| GET | /prediction/forecasts | Compara Extra Trees y promedio móvil de 6 meses por producto, escenario A/B y horizonte 1/3; `cutoff` opcional en formato AAAA-MM | M | ✅ |
| POST | /prediction/forecasts/explanation | Redacta con Gemini una explicación de ambos pronósticos; devuelve `source=gemini` o `fallback` | M | ✅ |

## Panel y reportes — `reports`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /dashboard/summary | Monto y pedidos de 12 meses, ticket, clientes, concentración y meses; alertas con aviso | M | ✅ |
| GET | /reports | Catálogo de reportes con el origen de sus datos | M | ✅ |
| GET | /reports/kpis | Valores disponibles sin metas ni estados inventados | M | ✅ parcial |
| GET | /reports/sales | Pedidos por mes, producto y categoría; precio pagado frente a la referencia (5 principales) y descuento en factura; filtro salesperson_code; margen sin datos de costos | M | ✅ |
| GET | /reports/customers | Concentración, maestro de clientes y top; riesgo y dormancia pendientes de reglas | M | ✅ parcial |
| GET | /reports/stock | Saldo por producto al último cierre, con aviso de campo sin confirmar y sin lotes; demanda de 12 meses, cobertura en días y estado por producto (umbrales provisionales) | M | ✅ parcial |
| GET | /reports/receivables | Cobrado en el período por mes y los 10 clientes que más pagaron (real); deuda pendiente y vencida en null con aviso `receipts_not_linked` | M | ✅ aviso |
| GET | /reports/salespeople | Monto, pedidos y clientes de 12 meses por vendedor; alertas pendientes | M | ✅ parcial |
| GET | /reports/funnel | Estructura sin cifras hasta definir alertas y conversión | M | ✅ aviso |

Las rutas con cifras aceptan `?from=&to=`; el catálogo `/reports` no necesita fechas.

Sin fechas, los 12 meses terminan en el último pedido cargado (`data_as_of`). Se excluyen líneas bonificadas,
productos no veterinarios y pedidos cancelados (C); esta regla de estados es provisional. Los montos son de pedidos,
sin IGV: no acreditan venta facturada. Cada cifra declara `data_origin=real`; si faltan datos se devuelve `null` y
un aviso. Los saldos del kardex están por confirmar, no hay costos para rentabilidad ni relación entre cobros y pedidos.

## Preguntas a los datos — `explanations`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| POST | /insights/questions | Pregunta en lenguaje natural; la respuesta sale de la base y lista sus fuentes | M | ✅ |
| POST | /insights/report-summary | Redacción opcional de KPIs, ventas, clientes, stock, cobranza, vendedores y panel a partir de métricas numéricas permitidas | M | ✅ |

Gemini solo elige una consulta de la lista cerrada (`prompts/insight_planner.md`) y redacta sobre las filas agregadas que devuelve `reports.public.run_allowed_query`. Hoy responden `sales_by_month`, `sales_by_family`, `top_products` y `salesperson_performance`; las demás devuelven 400 `query_not_available`. Una pregunta con RUC, DNI, correo, celular o nombre de cliente se rechaza (400 `identifies_customer`) antes de enviarse. Sin `GEMINI_API_KEY`: 400 `ai_unavailable`.

## Planificación de importación — `import_planning`
| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /import-suggestions | Cuatro laboratorios ficticios con escenario de importación ilustrativo | M | ✅ |
| PATCH | /import-suggestions/{suggestion_id} | Guarda la revisión `approved`, `rejected` o `pending`; no crea pedidos | M | ✅ |

Todo el escenario de esta versión está marcado `simulated`: nombres, productos, stock, demanda, precios, costos, vencimientos y fechas. Los siete CSV no identifican el laboratorio de cada producto ni traen costos de importación o lotes. Los datos se guardan en `import_laboratories` e `import_suggestions`, separados de Defontana; no se usa IA ni se crea una orden de compra. Los cuatro nombres ficticios se reemplazarán al recibir los reales.

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
| GET | /data-sources | Los 7 archivos: encabezados esperados, filas en la base, período y última carga confirmada | M | ✅ |
| POST | /data-imports | Subir un CSV con encabezados (multipart: `source`, `file`, `origin`); se valida, no se aplica | M | ✅ |
| GET | /data-imports | Cargas anteriores | M | ✅ |
| GET | /data-imports/{import_id} | Revisión: filas leídas y errores por línea | M | ✅ |
| PATCH | /data-imports/{import_id} | Confirmar (actualiza e inserta, nunca borra) o cancelar. Body: `{"action": "confirm" \| "cancel"}` | M | ✅ |

## Correo — `messaging`
Gerencia define el correo compartido de origen en Ajustes › Correo. Para dominios propios, el dominio debe estar
verificado en Resend. Cada usuario puede conectar su propio Gmail desde Perfil o el formulario de envío mediante
Google OAuth (permiso `gmail.send`), sin entregar una contraseña SMTP. Para activar esta opción, habilita Gmail API,
crea un cliente OAuth web y configura `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`GOOGLE_OAUTH_REDIRECT_URI`, `GOOGLE_OAUTH_TOKEN_KEY` y `FRONTEND_URL`. El URI de redirección debe coincidir
exactamente con el autorizado en Google Cloud. La clave de tokens se genera como indica `.env.example` y debe
conservarse al desplegar nuevas versiones. Los refresh tokens se cifran en la base de datos y cada conexión
pertenece a un usuario. La configuración SMTP previa se conserva solo para un correo Gmail compartido ya autorizado.
Sin `RESEND_API_KEY`, los envíos por Resend se simulan.
El permiso `gmail.send` es sensible; para uso público Google puede exigir la verificación de la aplicación OAuth.

| Método | Ruta | Para qué | Roles | Estado |
|---|---|---|---|---|
| GET | /email-senders | Remitentes permitidos y si su proveedor está configurado | M, S | ✅ |
| POST | /email-senders | Agregar remitente (dirección o dominio) | M | ✅ |
| PUT | /email-senders/{sender_id} | Editar remitente o marcarlo por defecto | M | ✅ |
| DELETE | /email-senders/{sender_id} | Quitar remitente | M | ✅ |
| GET | /gmail/connection | Estado de la conexión Gmail del usuario autenticado | M, S | ✅ |
| GET | /gmail/connect | Iniciar autorización con Google; devuelve URL de autorización | M, S | ✅ |
| GET | /gmail/callback | Recibir autorización de Google y regresar a la app | Google | ✅ |
| DELETE | /gmail/connection | Desconectar Gmail del usuario autenticado | M, S | ✅ |
| POST | /emails | Enviar: `sender_id=null` usa el Gmail propio; un ID usa el correo compartido. Para, asunto, mensaje y adjuntos en base64 | M, S | ✅ |

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
