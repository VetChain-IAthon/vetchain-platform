# Contrato de capas: dominio e infraestructura

Este documento va antes del contrato de endpoints (`endpoints.md`). Define qué vive en cada capa de cada
módulo, qué interfaces (puertos) conectan las capas y cómo se hablan los módulos entre sí.
Los endpoints solo son la capa de entrada; la lógica del negocio vive en el dominio.

## 1. Las cuatro capas de cada módulo

```
app/modules/<module>/
  domain/           lo que el negocio ES: entidades, objetos de valor, reglas, puertos (interfaces)
  application/      lo que el sistema HACE: casos de uso; coordina dominio y puertos
  infrastructure/   cómo se conecta al mundo: base de datos, Gemini, XGBoost, CSV, reloj
  interface/        cómo se expone: rutas FastAPI y esquemas HTTP
```

| Capa | Contiene | Puede importar | Nunca importa |
|---|---|---|---|
| domain | Entidades, objetos de valor, servicios de dominio, puertos (`Protocol`), errores de negocio | Solo Python estándar y el núcleo compartido (shared_kernel) | FastAPI, SQLAlchemy, Pydantic, requests, google-genai, xgboost |
| application | Casos de uso (una clase por caso, método `execute`), comandos y consultas (dataclasses), `public.py` | domain y shared_kernel | FastAPI, SQLAlchemy, Pydantic, infrastructure |
| infrastructure | Implementaciones de los puertos: repositorios SQLAlchemy, modelos ORM, mapeadores, clientes externos | domain, application y las librerías | interface |
| interface | Routers, esquemas Pydantic de entrada y salida, dependencias de FastAPI | application, shared_kernel y FastAPI | infrastructure (salvo en el cableado) |

**Regla de dependencia:** las flechas apuntan hacia el dominio.
`interface → application → domain ← infrastructure`. El dominio no sabe que existen la base de datos ni HTTP.

## 2. Reglas que no se rompen

- **Dominio puro.** Entidades como `dataclass` normales. Los modelos ORM existen solo en
  `infrastructure/orm.py`; un mapper convierte entre ORM y entidad. Pydantic existe solo en `interface/schemas.py`.
- **Puertos en el dominio, adaptadores en infraestructura.** El dominio declara `class UserRepository(Protocol)`;
  `infrastructure/repositories.py` la implementa con SQLAlchemy.
- **Un caso de uso por acción del usuario.** `application/use_cases.py` (o una carpeta si crece) con clases como
  `IssueQuotation`. Cada ruta llama a un solo caso de uso. El caso de uso abre la transacción (Unit of Work).
- **Entre módulos solo por `public.py`.** Un módulo expone a los demás únicamente `application/public.py`
  (funciones o una clase fachada con tipos simples). Nadie importa el domain, la infrastructure ni el ORM de otro módulo.
- **Anticorrupción.** Si `customers` necesita datos de `prediction`, declara un puerto propio (`PredictionGateway`)
  en su dominio. Su infraestructura lo implementa llamando a `prediction.application.public`.
  Así `customers` no depende de cómo `prediction` guarda o calcula.
- **Tablas de los CSV.** Las escribe solo `data_imports` (upsert). Las demás las leen mediante repositorios
  de lectura propios de cada módulo; ninguno las modifica.
- **Errores de negocio en el dominio, códigos HTTP en la interfaz.** El dominio lanza `BusinessRuleError`,
  `NotFoundError`, `ForbiddenError` o `ConflictError`; la interfaz los traduce a 400, 404, 403 y 409
  (ver `app/core/errors.py`). El dominio nunca habla de códigos HTTP.
- **Sin PDF ni formato de presentación en el backend:** dinero como número, fechas ISO.

### Dependencias permitidas entre módulos

| Módulo | Puede llamar a (por `public.py`) |
|---|---|
| customers | prediction, explanations, settings |
| quotations | settings, customers (condiciones comerciales) |
| import_planning | prediction |
| data_imports | quotations (`match_conversions`) |
| reports | settings (días de crédito), data_imports (origen del dato) |
| explanations | reports (ejecutar consultas permitidas) |
| auth, settings, prediction | ninguno |

**Evitar ciclos.** Si dos módulos se necesitan, el dato compartido sube al shared_kernel o se pasa como parámetro.
Ver el punto abierto 1 en la sección 9.

## 3. Núcleo compartido (shared_kernel)

Vive en `app/core/`. Solo tipos pequeños y estables, sin lógica de ningún módulo.

| Pieza | Capa | Detalle |
|---|---|---|
| `Money` | dominio | Soles (PEN), `Decimal` con 2 decimales. Operaciones suma, resta, porcentaje. Sin IGV salvo que el nombre lo diga |
| `Percentage` | dominio | 0 a 100, validado |
| `Ruc` | dominio | 11 dígitos, validado |
| `DataOrigin` | dominio | `real`, `synthetic`, `estimated`, `simulated` |
| `DateRange` | dominio | `from`, `to`; `from <= to` |
| `Clock` | puerto | `today()`, `now()`. Implementación del sistema y una fija para pruebas |
| `UnitOfWork` | puerto | `commit()`, `rollback()`; una sesión por caso de uso |
| `BusinessRuleError`, `NotFoundError`, `ForbiddenError`, `ConflictError` | dominio | Errores base |
| `Page[T]`, `Paging` | aplicación/interfaz | Forma de las listas (`items`, `total`, `page`, `per_page`) |
| Motor y sesión de BD (`app/core/database.py`), `SqlAlchemyUnitOfWork` y ORM de Defontana (`app/infrastructure/db/`), `SystemClock` | infraestructura | Compartidos por todos los módulos. Ver [`infraestructura.md`](infraestructura.md) |

## 4. Mapa por módulo

Formato: **Dominio** (entidades, objetos de valor, reglas, servicios) · **Puertos** (en el dominio) ·
**Casos de uso** (y su endpoint) · **Infraestructura** (adaptadores y tablas) · **Fachada pública** (para otros módulos).

### auth
- **Dominio:** `User` (id, email, full_name, phone, role, salesperson_code, active).
  Objetos de valor: `Email`, `Role` (`manager` | `salesperson`).
  Reglas: un `salesperson` debe tener `salesperson_code`; un usuario inactivo no inicia sesión; el correo es único.
- **Puertos:** `UserRepository`, `PasswordHasher`, `TokenService`.
- **Casos de uso:** `CreateSession` (POST /sessions) · `GetCurrentUser` (GET /me) · `UpdateOwnProfile` (PATCH /me) ·
  `ListUsers` (GET /users) · `CreateUser` (POST /users) · `UpdateUser` (PATCH /users/{id}).
- **Infraestructura:** `SqlAlchemyUserRepository` (tabla `users`) · `Pbkdf2PasswordHasher` (hashlib) · `JwtTokenService` (pyjwt).
- **Fachada pública:** `authenticate_token(token) -> CurrentUser(id, role, salesperson_code)`.

### customers
- **Dominio:**
  - Entidades: `Customer` (solo lectura; viene de los CSV), `Alert` (raíz: id, ruc, fecha, probabilidad,
    dinero en juego, motivos, producto habitual, producto cruzado), `Contact` (ruc, usuario, alerta opcional, resultado, fecha).
  - Objetos de valor: `Level` (A/B/C), `CustomerStatus` (active/at_risk/dormant), `PurchaseRhythm` (días promedio
    entre pedidos), `Probability`, `ContactOutcome` (5 opciones por definir con Mederi), `SalespersonScope`.
  - Servicios de dominio: `LevelClassifier` (nivel según monto de 12 meses y umbrales), `DormancyEvaluator`
    (días desde el último pedido frente al ritmo), `AlertPrioritizer` (dinero en juego = venta de 12 meses ÷ pedidos),
    `WhatsappLinkBuilder`.
  - Reglas: una alerta por cliente y día; un contacto exige resultado; el vendedor solo opera sobre su cartera.
- **Puertos:** `CustomerReadRepository`, `AlertRepository`, `ContactRepository`, `PredictionGateway`,
  `ExplanationGateway`, `SettingsGateway`, `Clock`.
- **Casos de uso:** `ListCustomers`, `GetCustomer`, `ListCustomerOrders`, `ListCustomerProducts`, `GetCommercialTerms`,
  `ListContacts`, `RegisterContact`, `BuildWhatsappLink`, `GetCustomerBrief` (los 9 endpoints de /customers) ·
  `GenerateDailyAlerts` (tarea diaria, sin endpoint) · `ListAlerts`, `GetAlertsSummary`, `GetAlert`,
  `GetAlertExplanation` (los 4 de /alerts).
- **Infraestructura:** repositorios SQLAlchemy sobre `customers`, `orders`, `order_lines` (lectura) y `alerts`,
  `contacts` (escritura) · adaptadores de los gateways que llaman a prediction, explanations y settings por su `public.py`.
- **Fachada pública:** `get_commercial_terms(ruc) -> CommercialTerms(level, margin_pct, max_discount_pct, credit_days)`.

### explanations
- **Dominio:** `AggregatedFigures` (días sin comprar, frecuencia, probabilidad, monto promedio, familias): por
  construcción no tiene nombre ni RUC. `InsightQuery` (tipo permitido + filtros) con `AllowedQueryType` (lista cerrada).
  `Explanation` (texto + origen `ai` | `fallback`), `InsightAnswer` (texto + fuentes + data_origin).
  Servicio de dominio: `PrivacyGuard` (rechaza cualquier texto o filtro que identifique a un cliente).
  Reglas: Gemini solo recibe `AggregatedFigures`; en preguntas libres solo convierte la pregunta en un
  `InsightQuery` permitido; la respuesta sale de la base.
- **Puertos:** `TextGenerator`, `QueryPlanner`, `InsightQueryRunner`, `FallbackTextBuilder`, `PromptRepository`.
- **Casos de uso:** `ExplainAlert` (lo usa GET /alerts/{id}/explanation) · `AskInsightQuestion` (POST /insights/questions).
- **Infraestructura:** `GeminiTextGenerator` y `GeminiQueryPlanner` (google-genai) · `FilePromptRepository`
  (lee `prompts/*.md`) · `ReportsInsightQueryRunner` (llama a `reports.public`) · `TemplateFallbackTextBuilder`.
- **Fachada pública:** `explain_alert(figures: AggregatedFigures) -> Explanation`.

### settings
- **Dominio:** `PricingSettings` (tasa de IGV, vigencia en días, margen mínimo, rebaja en promociones),
  `CustomerLevelRule` (nivel, descuento máximo, margen, días de crédito), `LevelThresholds` (monto mínimo para B y para A).
  Servicio de dominio: `LevelPolicy.classify(amount_12m) -> Level`.
  Reglas: porcentajes entre 0 y 100; umbral de A mayor o igual que el de B; siempre existen los niveles A, B y C.
- **Puertos:** `SettingsRepository`.
- **Casos de uso:** `GetPricing`, `ReplacePricing`, `ListCustomerLevels`, `ReplaceCustomerLevel`,
  `GetLevelThresholds`, `ReplaceLevelThresholds` (los 6 de /settings).
- **Infraestructura:** `SqlAlchemySettingsRepository` (tablas `pricing_settings`, `customer_levels`, `level_thresholds`).
- **Fachada pública:** `get_pricing()`, `get_level_rules()`, `classify_level(amount_12m)`.

### quotations
- **Dominio:** `Quotation` (raíz del agregado; líneas, estado, aprobación, vigencia, order_id), `QuotationLine`,
  `Product` (lectura). Objetos de valor: `QuotationStatus` (issued/converted/expired), `ReferencePrice` (precio + origen),
  `Margin` (puede ser nulo), `ApprovalStatus` (requerida, confirmada, nota).
  Servicios de dominio: `QuotationPricer` (subtotal, IGV, total, margen), `ApprovalPolicy` (requiere aprobación si el
  descuento supera el máximo del nivel o el margen baja del mínimo), `ConversionMatcher` (pedido del mismo cliente con
  fecha entre la emisión y la vigencia).
  Reglas: mínimo una línea; cantidad mayor que cero; no se emite si requiere aprobación y no está confirmada
  (error de negocio, 400); una cotización emitida no se edita; `valid_until` = fecha de emisión + vigencia;
  sin costos el margen es nulo con aviso `no_cost_data`.
- **Puertos:** `QuotationRepository`, `ProductCatalog` (productos y último precio pagado), `OrderLookup`
  (pedidos posteriores a una fecha), `CustomerTermsGateway`, `SettingsGateway`, `Clock`.
- **Casos de uso:** `SearchProducts`, `GetProduct` (GET /products) · `PreviewQuotation` (POST /quotation-previews) ·
  `IssueQuotation` (POST /quotations) · `ListQuotations`, `GetQuotation` (GET /quotations) ·
  `MatchConversions` (sin endpoint; lo dispara data_imports).
- **Infraestructura:** `SqlAlchemyQuotationRepository` (tablas `quotations`, `quotation_lines`) · `SqlProductCatalog`
  (`products`, `order_lines`) · `SqlOrderLookup` (`orders`) · gateways hacia `customers.public` y `settings.public`.
- **Fachada pública:** `match_conversions() -> ConversionResult(converted, expired)`.

### prediction
- **Dominio:** `CustomerFeatures` (días desde el último pedido, frecuencia, monto, familias), `RepurchaseProbability`
  (0 a 1), `ModelInfo` (versión, fecha de entrenamiento, AUC, precisión en el 10 % superior), `DemandForecast`
  (producto, mes, cantidad, origen).
  Reglas: sin modelo cargado se lanza un error de negocio claro, no se inventan valores; el pronóstico lleva data_origin.
- **Puertos:** `RepurchaseModel` (`predict(features)`), `FeatureReader`, `ModelInfoRepository`, `DemandReader`.
- **Casos de uso:** `GetModelInfo` (GET /prediction/model) · `PredictRepurchase`, `ForecastDemand`
  (internos, los usan otros módulos).
- **Infraestructura:** `XgboostRepurchaseModel` (carga `models/model.json`, usa numpy) · `SqlFeatureReader`
  (`orders`, `order_lines`) · `JsonModelInfoRepository` (`models/model_info.json`) · `SqlDemandReader`.
- **Fachada pública:** `predict_many(rucs) -> dict[ruc, probability]`, `forecast_demand(product_codes, months)`.

### reports
- **Dominio:** `Kpi` (código, valor, meta, estado ok/warn/critical, data_origin), `ReportSection`, `Funnel` (alertas,
  contactos, cotizaciones, convertidas, monto recuperado), `AgingBucket` (antigüedad de la deuda), `DataOriginSet`.
  Servicios de dominio: `KpiEvaluator`, `AgingCalculator` (estima el vencimiento con los días de crédito del nivel,
  marcado `estimated`), `RecoveredAmountCalculator`.
  Reglas: toda cifra lleva data_origin; sin datos o costos suficientes se devuelve un aviso, no un valor;
  "venta" = pedidos mientras no se confirmen los estados A, C y D.
- **Puertos:** `SalesReadRepository`, `CustomersReadRepository`, `StockReadRepository`, `ReceivablesReadRepository`,
  `FunnelReadRepository`, `DataOriginProvider`, `SettingsGateway`.
- **Casos de uso:** `GetDashboardSummary`, `ListReports`, `GetKpis`, `GetSalesReport`, `GetCustomersReport`,
  `GetStockReport`, `GetReceivablesReport`, `GetSalespeopleReport`, `GetFunnelReport`
  (los 9 endpoints de /dashboard y /reports).
- **Infraestructura:** consultas SQL de agregación de solo lectura (SQLAlchemy Core, sin entidades ni pandas) ·
  `ImportsDataOriginProvider` (llama a `data_imports.public`).
- **Fachada pública:** `run_allowed_query(query: InsightQuery) -> AggregatedResult` (para explanations).

### import_planning
- **Dominio:** `ImportSuggestion` (raíz: producto, proveedor opcional, cantidad sugerida, pedir antes de, decisión,
  data_origin), `Decision` (pending/approved/rejected), `CoveragePolicy` (las reglas fijas que la IA no puede saltarse:
  cobertura mínima y máxima).
  Reglas: una decisión puede deshacerse (vuelve a pending); solo la demanda mensual es real, el resto es `simulated`.
- **Puertos:** `ImportSuggestionRepository`, `DemandGateway`, `StockReader`.
- **Casos de uso:** `ListImportSuggestions`, `DecideImportSuggestion` (los 2 de /import-suggestions).
- **Infraestructura:** `SqlAlchemyImportSuggestionRepository` (tabla `import_suggestions`) · `PredictionDemandGateway`
  (llama a `prediction.public`) · `SqlStockReader` (`stock_balances`).
- **Fachada pública:** ninguna.

### data_imports
- **Dominio:** `DataImport` (raíz: id, fuente, origen, estado, filas leídas, filas con error, fechas), `DataSource`
  (siete fuentes) con su `CsvSchema` (columnas y tipos), `RowError` (línea y motivo).
  Servicios de dominio: `CsvRowValidator`, `ImportStateMachine` (staged → confirmed | cancelled).
  Reglas: solo una carga `staged` se confirma o se cancela; confirmar actualiza e inserta, nunca borra;
  cada carga declara su origen (`real`, `synthetic`, `simulated`).
- **Puertos:** `DataImportRepository`, `CsvReader`, `StagingStore` (guarda las filas validadas hasta confirmar),
  `SourceDataWriter` (upsert por fuente), `DataOriginRegistry`, `ConversionNotifier`.
- **Casos de uso:** `ListDataSources` (GET /data-sources) · `StageImport` (POST /data-imports) · `ListImports`,
  `GetImport` (GET /data-imports) · `ConfirmImport`, `CancelImport` (PATCH /data-imports/{id}).
  Al confirmar una carga de `orders`, `ConfirmImport` llama a `ConversionNotifier`.
- **Infraestructura:** `StdlibCsvReader` (módulo csv) · `SqlAlchemyDataImportRepository` (tabla `data_imports`) ·
  `SqlStagingStore` (decidir: tabla de paso o archivo en `data/staging/`) · `SqlSourceDataWriter` (upsert en
  `customers`, `salespeople`, `products`, `orders`, `order_lines`, `stock_balances`, `receipts`; hoy lo hace `app/infrastructure/loaders/defontana_csv.py`) ·
  `QuotationsConversionNotifier` (llama a `quotations.public`).
- **Fachada pública:** `get_data_origin(source) -> DataOrigin`, `list_last_confirmed() -> list[SourceStatus]`.

## 5. Cableado (dónde se juntan las capas)

- Cada módulo tiene `interface/dependencies.py`, que arma los casos de uso: crea los adaptadores de infrastructure
  y se los entrega al caso de uso. Es el único lugar de la interfaz que conoce la infraestructura (FastAPI `Depends`).
- `app/main.py` solo monta los routers, el manejo de errores y la configuración.
- Una sesión de base de datos por petición; el caso de uso la usa mediante el `UnitOfWork`.
  Las tareas diarias (alertas) arman su propio cableado.

## 6. Pruebas por capa

| Capa | Cómo se prueba | Necesita |
|---|---|---|
| domain | Pruebas unitarias puras | Nada: sin base de datos ni red |
| application | Casos de uso con puertos falsos en memoria | Fakes del dominio |
| infrastructure | Repositorios contra SQLite; adaptadores externos con respuestas simuladas | SQLite |
| interface | `TestClient` de FastAPI | La app completa |

Además: prueba de arquitectura (`tests/test_architecture.py`) que falla si domain o application importan FastAPI,
SQLAlchemy, Pydantic o infrastructure, o si un módulo importa el domain, la infrastructure o el ORM de otro módulo.

## 7. Convenciones de nombres

| Pieza | Convención | Ejemplo |
|---|---|---|
| Entidad / objeto de valor | Sustantivo del negocio | `Quotation`, `ReferencePrice` |
| Servicio de dominio | Rol, sin la palabra Service | `ApprovalPolicy`, `AgingCalculator` |
| Puerto | Qué ofrece, sin prefijo I | `UserRepository`, `TextGenerator` |
| Adaptador | Tecnología + puerto | `SqlAlchemyUserRepository`, `GeminiTextGenerator` |
| Caso de uso | Verbo + objeto | `IssueQuotation`, `ConfirmImport` |
| Gateway entre módulos | `<Módulo>Gateway` (puerto) | `PredictionGateway` |
| Modelo ORM | Sufijo `Row` en `orm.py` | `QuotationRow` |
| Esquema HTTP | Sufijo `In` / `Out` | `QuotationCreateIn`, `QuotationOut` |
| Código y rutas | Inglés. Mensajes al usuario en español | |

## 8. Del esqueleto actual a las capas

El esqueleto está en estructura plana. Al construir cada módulo se mueve así:

| Hoy | Pasa a |
|---|---|
| `router.py`, `schemas.py` | `interface/router.py`, `interface/schemas.py` |
| `service.py` | `application/use_cases.py` (y las reglas puras a `domain/services.py`) |
| `models.py` (tablas SQLAlchemy) | `infrastructure/orm.py` (las entidades van aparte en `domain/entities.py`) |
| ~~`app/core/mederi_tables.py`~~ | Hecho: ORM en `app/infrastructure/db/source_models.py`; `app/core/source_tables.py` queda como re-export |
| ~~`app/core/deps.py`~~ | Hecho: `app/core/auth.py` (`current_user`, `require_role`, `forced_salesperson_code`), compartido por las interfaces; usa `auth.application.public` |
| ~~`app/core/security.py`~~ | Hecho: `auth/infrastructure/security.py` (`Pbkdf2PasswordHasher`, `JwtTokenService`) |
| ~~`app/core/errors.py` (nuevo)~~ | Hecho: traduce los errores del dominio; además `app/core/stubs.py` (501) y `app/core/schemas.py` (`JsonNumber`) |

Renombres pendientes en el código para alinearlo con este contrato:

| Hoy en el código | Según el contrato |
|---|---|
| ~~Módulos `pricing`, `quotes`, `planning`, `data_import`~~ | Hecho: `settings`, `quotations`, `import_planning`, `data_imports`. El esqueleto plano se eliminó: cada módulo tiene solo `__init__.py` y sus capas |
| ~~Roles `management`, `sales_rep`~~ | Hecho: `manager`, `salesperson` |
| ~~`sales_rep_code`~~ | Hecho: `salesperson_code` (migración `bc3d285b5ffb`) |
| ~~Tablas `sales_reps`, `order_items`, `kardex`, `payments`~~ | Hecho: `salespeople`, `order_lines`, `stock_balances`, `receipts` (ver `base-de-datos.md`) |
| ~~Tablas `customer_tiers`, `customer_rebates`~~ | Hecho: `customer_levels`, `pricing_settings`, `level_thresholds`; las rebajas por cliente se eliminaron |
| ~~Tablas `quotes`, `quote_lines`~~ | Eliminadas. `quotations` y `quotation_lines` se crean al construir quotations |
| ~~Rutas `/api/<module>/...` y `GET /status`~~ | Hecho: `/api/v1/<recurso>` según `endpoints.md`; solo `/health` fuera del prefijo |

## 9. Puntos abiertos

1. **Hay un ciclo entre módulos.** Con la tabla de dependencias de la sección 2 se forma
   customers → explanations → reports → data_imports → quotations → customers.
   Propuesta: que `quotations` no llame a `customers`, sino que reciba las condiciones comerciales como parámetro
   o las lea de `settings` con el nivel ya calculado. Otra opción es que `data_imports` publique un evento
   "pedidos confirmados" en vez de llamar a `quotations`.
2. **Tipos de dominio que cruzan módulos.** `explain_alert(figures: AggregatedFigures)` obliga a `customers` a
   importar un tipo del dominio de `explanations`, y `run_allowed_query(query: InsightQuery)` obliga a `reports`
   a importar otro. Las dos cosas van contra la regla "nadie importa el domain de otro".
   Propuesta: que `public.py` reciba y devuelva DTO propios (dataclasses simples definidos en `public.py`), o subir
   esos tipos al shared_kernel.
3. ~~El shared_kernel mezcla dominio e infraestructura en `app/core/`.~~ **Resuelto:** la parte pura vive en
   `app/core/domain/` (tipos, errores, `Clock`, `UnitOfWork`) y `app/core/application/` (`Page`, `Paging`).
   La infraestructura compartida (`SqlAlchemyUnitOfWork`, ORM de Defontana, cargador) vive en `app/infrastructure/`.
4. ~~`endpoints.md` no está en el repositorio~~ **Resuelto:** `docs/endpoints.md` sigue este contrato (sin PDF,
   cotizaciones sin edición, `/prediction/model`, 9 rutas de reports). Sus cambios están al final del documento. Los choques eran:
   - Tiene endpoints `/pdf`, pero este contrato dice "sin PDF en el backend".
   - Los estados de cotización allí son `sent`/`accepted`/`lost`, con `PUT`/`PATCH` para editar. Aquí son
     `issued`/`converted`/`expired` y una cotización emitida no se edita.
   - Aquí aparece `GET /prediction/model`, que allí no está.
   - Aquí `reports` tiene 9 casos de uso, pero allí /dashboard y /reports suman 11 endpoints.
5. ~~Rebajas por cliente~~ **Resuelto:** `customer_rebates` se eliminó (migración `bc3d285b5ffb`), porque el contrato no lo incluye.
6. **Estados de pedido:** documentados en `dudas-mederi.md`. La regla de venta es provisional: excluye los cancelados (C).
7. **Por definir con Mederi:** las 5 opciones de `ContactOutcome`.
8. **Por decidir:** dónde guarda las filas `StagingStore`, en una tabla de paso o en `data/staging/`.
9. **Decisiones tomadas al implementar el dominio (a validar):**
   - Se agregó `UnauthorizedError` (401) a los errores base, para sesiones inválidas o vencidas.
   - Cada módulo tiene su propia copia de los tipos que recibe de otro (por ejemplo `Level`, `CommercialTerms`),
     así no importa el dominio ajeno. Los gateways traducen.
   - `DormancyEvaluator` recibe los factores de "en riesgo" y "dormido" y un ritmo por defecto sin valores fijos:
     hay que definirlos con gerencia (¿irán en settings?).
   - `RecoveredAmountCalculator`: monto recuperado = pedidos de clientes contactados dentro de N días del contacto.
   - `AllowedQueryType` tiene una lista inicial de 8 consultas, que hay que validar con gerencia.
   - `CoveragePolicy`: si el stock cubre menos que el mínimo, se pide hasta el máximo; un mes cuenta como 30 días.
   - Un usuario no puede desactivarse a sí mismo, y un producto no se repite dentro de una cotización.
   - Los CSV aceptan fechas `AAAA-MM-DD` o `DD/MM/AAAA` y decimales con punto. Hay que confirmarlo con los archivos reales.
10. **Diferencias entre el dominio y los datos reales (aparecieron al construir la infraestructura):**
    - ~~`Ruc` exige 11 dígitos~~ **Resuelto:** acepta de 8 a 15 dígitos y expone `kind` (company, person, other),
      porque 12 clientes activos tienen DNI (ver `dudas-mederi.md`).
    - ~~`data_imports/domain/sources.py` con columnas anteriores~~ **Resuelto:** usa el mapa real por posición, y
      `tests/test_module_repositories.py` verifica que coincida con el cargador.
    - La regla de venta (`SalesDefinition`) excluye por defecto los pedidos cancelados (C), igual que las consultas.
      Es provisional hasta que Mederi confirme los estados T y D.
    - Los cobros (`receipts`) no se enlazan con pedidos: `Receivable` y `AgingCalculator` de reports no tienen datos
      reales hasta que llegue el CSV de comprobantes.
    - `order_id` pasó a `order_no` en quotations, customers y reports.
