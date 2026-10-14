# Capas de aplicación y presentación

Complementa [`capas.md`](capas.md), que cubre dominio e infraestructura, y [`endpoints.md`](endpoints.md), que es el
contrato HTTP. Explica la capa de aplicación (casos de uso) y la de interfaz o presentación (endpoints).

```
interface  →  application  →  domain  ←  infrastructure
(HTTP)        (casos de uso)   (reglas)    (BD, Gemini, XGBoost, CSV)
```

Módulos de referencia ya construidos en las cuatro capas: **`auth`** y **`settings`**. El resto tiene dominio (y
customers y reports, repositorios), y sus rutas responden 501.

## 1. Capa de aplicación: qué hace el sistema

Cada acción del usuario es un caso de uso: una clase con un método `execute`. El caso de uso coordina; no decide reglas
ni habla con la base. Sus pasos son:
1. Recibe un comando (cambia algo) o una consulta (solo lee) como dataclass simple. En auth están en `application/commands.py`.
2. Abre la transacción con el `UnitOfWork` (`with self.uow:`).
3. Pide datos a los puertos (repositorios y gateways).
4. Llama al dominio, donde viven las reglas.
5. Guarda con el puerto y hace `commit`.
6. Devuelve un resultado simple (dataclass o tipos del dominio), nunca un modelo ORM ni un esquema Pydantic.

Ejemplo real, `auth/application/use_cases.py`:

```python
class CreateUser:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, salespeople: SalespersonDirectory, uow: UnitOfWork): ...

    def execute(self, command: CreateUserCommand) -> User:
        with self.uow:
            PasswordPolicy.check(command.password)                                   # dominio
            email = Email(command.email)                                             # dominio
            UserRules.ensure_email_available(self.users.get_by_email(email))         # puerto + dominio
            code = (command.salesperson_code or "").strip() or None
            UserRules.ensure_salesperson_exists(code, code is not None and self.salespeople.exists(code))
            user = User(email=email, full_name=command.full_name, role=_role(command.role),
                        password_hash=self.hasher.hash(command.password), ...)       # el dominio valida el rol
            user = self.users.add(user)                                              # puerto
            self.uow.commit()
            return user
```

### Reglas
- Un caso de uso por acción del usuario. Cada ruta llama a un solo caso de uso.
- La capa de aplicación importa solo `domain` y el shared_kernel (`app.core.domain`, `app.core.application`). Nunca
  FastAPI, SQLAlchemy, Pydantic ni infrastructure. Lo verifica `tests/test_architecture.py`.
- La transacción se abre aquí, no en la ruta ni en el repositorio.
- No se escriben reglas de negocio aquí: si hay un `if` de negocio, va al dominio (entidad o servicio de dominio).
- Entre módulos solo por `application/public.py`, con funciones y tipos simples, por ejemplo
  `settings.public.get_pricing() -> PricingTerms`.
- **Cómo se cablea una fachada pública sin conocer la infraestructura:** `public.py` tiene `configure(...)`, y la
  interfaz del módulo lo llama al cargarse. Por ejemplo, `auth/interface/dependencies.py` hace
  `public.configure(authenticate)` y `settings/interface/dependencies.py` hace `public.configure(_scope)`.
- Las tareas sin endpoint también son casos de uso: `GenerateDailyAlerts` y `MatchConversions`.
- Los errores de negocio los lanza el dominio (`BusinessRuleError`, `NotFoundError`, `ForbiddenError`,
  `ConflictError`, `UnauthorizedError`). El caso de uso no los convierte en HTTP.

### Casos de uso por módulo

| Módulo | Casos de uso | Endpoints | Estado |
|---|---|---|---|
| auth | CreateSession, GetCurrentUser, UpdateOwnProfile, ListUsers, CreateUser, UpdateUser; interno: AuthenticateToken | /sessions, /me, /users | ✅ |
| settings | GetPricing, ReplacePricing, ListCustomerLevels, ReplaceCustomerLevel, GetLevelThresholds, ReplaceLevelThresholds; internos: GetCompleteLevelRules, ClassifyLevel | /settings/* | ✅ |
| customers | ListCustomers, GetCustomer, ListCustomerOrders, ListCustomerProducts, GetCommercialTerms, ListContacts, RegisterContact, BuildWhatsappLink, GetCustomerBrief, ListAlerts, GetAlertsSummary, GetAlert, GetAlertExplanation; sin endpoint: GenerateDailyAlerts | /customers, /alerts | ⏳ (repositorio hecho) |
| explanations | ExplainAlert, AskInsightQuestion | /insights/questions (ExplainAlert lo usa /alerts/{id}/explanation) | ⏳ |
| quotations | SearchProducts, GetProduct, PreviewQuotation, IssueQuotation, ListQuotations, GetQuotation; sin endpoint: MatchConversions | /products, /quotation-previews, /quotations | ⏳ |
| prediction | GetModelInfo; internos: PredictRepurchase, ForecastDemand | /prediction/model | ⏳ |
| reports | GetDashboardSummary, ListReports, GetKpis, GetSalesReport, GetCustomersReport, GetStockReport, GetReceivablesReport, GetSalespeopleReport, GetFunnelReport | /dashboard/summary, /reports/* | ⏳ (repositorios hechos) |
| import_planning | ListImportSuggestions, DecideImportSuggestion | /import-suggestions | ⏳ |
| data_imports | ListDataSources, StageImport, ListImports, GetImport, ConfirmImport, CancelImport | /data-sources, /data-imports | ⏳ |

`data_imports` escribe con upsert en salespeople, customers, products, orders, order_lines, stock_balances y receipts.
`ConfirmImport` debe reutilizar el parser y la política de vacíos de `app/infrastructure/loaders/defontana_csv.py`.

## 2. Capa de interfaz (presentación): cómo se expone

Es la única capa que sabe de HTTP. Traduce una petición en un comando, llama a un caso de uso y traduce el resultado
a una respuesta.

```
app/modules/<modulo>/interface/
  router.py         rutas FastAPI (una función delgada por endpoint)
  schemas.py        esquemas Pydantic de entrada y salida (sufijos In / Out)
  dependencies.py   cableado: crea los adaptadores y arma los casos de uso (Depends); registra la fachada pública
```

Ejemplo real, `auth/interface/router.py`:

```python
@router.post("/users", response_model=UserOut, status_code=201, tags=["usuarios"])
def create_user(body: UserCreateIn,
                _: SessionUser = Depends(manager_only),
                use_case: CreateUser = Depends(deps.get_create_user)):
    command = CreateUserCommand(body.email, body.full_name, body.role, body.password, body.phone, body.salesperson_code)
    return UserOut.from_domain(use_case.execute(command))
```

### Responsabilidades

| Responsabilidad | Dónde | Detalle |
|---|---|---|
| Validar formato | `interface/schemas.py` | Formato inválido = 422 (lo valida FastAPI) |
| Reglas de negocio | dominio | Regla rota = 400, con el error de negocio traducido |
| Autenticación | `app/core/auth.py` → `current_user` | JWT en `Authorization: Bearer`. Todo exige sesión salvo `POST /sessions` y `GET /health` |
| Autorización por rol | `app/core/auth.py` → `require_role(MANAGER)` | Roles `manager` y `salesperson` |
| Alcance del vendedor | `app/core/auth.py` → `forced_salesperson_code(user, requested)` | Para el vendedor se fuerza su propio código, sin confiar en la web |
| Errores | `app/core/errors.py` | 400 / 401 / 403 / 404 / 409 / 422 / 501 con la forma `{"error": {"code", "message", "details"}}` |
| Listas | `Page[T]` | `{"items", "total", "page", "per_page"}` |
| Números | `app/core/schemas.py` → `JsonNumber` | Decimal adentro, número en el JSON (Pydantic v2 lo serializaría como texto) |
| Origen del dato | esquemas de salida | Toda cifra lleva `data_origin` |
| Documentación | FastAPI | Swagger en `/docs`, ReDoc en `/redoc`, `docs/openapi.json` (con prueba que lo mantiene al día) |

### Reglas
- Las rutas son delgadas: sin SQL, sin reglas de negocio, sin cálculos.
- Pydantic vive solo en `interface/schemas.py`.
- `dependencies.py` es el único lugar de la interfaz que conoce la infraestructura. Usa la sesión de la petición
  (`get_db`) para los repositorios y para `SqlAlchemyUnitOfWork(session=db)`.
- `CurrentUser` entre módulos es `app.core.application.SessionUser` (id, role, salesperson_code), con tipos simples.
- Un endpoint aún no construido se registra con `add_pending_route(...)` (`app/core/stubs.py`): exige sesión y rol, y
  responde 501. Así el contrato existe desde el inicio.
- Si se agrega o cambia una ruta, hay que actualizar `docs/endpoints.md` (lo verifica `tests/test_contract.py`) y
  `docs/openapi.json` con `python -m scripts.export_openapi` (lo verifica `tests/test_openapi.py`).

## 3. Recorrido de una petición (`PATCH /api/v1/users/{id}`)
1. **interface:** Pydantic valida el cuerpo (422 si el formato es malo). `require_role(MANAGER)` verifica el token
   (401) y el rol (403).
2. **interface:** la ruta arma `UpdateUserCommand` y llama a `UpdateUser.execute`.
3. **application:** abre el `UnitOfWork`, carga el usuario (404 si no existe) y verifica que el vendedor exista.
4. **domain:** `User.change_role` exige código para un vendedor (400) y `User.deactivate` impide desactivarse a sí mismo (409).
5. **infrastructure:** `SqlAlchemyUserRepository.save`, luego `uow.commit()`.
6. **interface:** el resultado se convierte en `UserOut`, o el error en la forma estándar.

## 4. Cómo se prueba cada capa

| Capa | Cómo | Dónde |
|---|---|---|
| domain | Pruebas unitarias puras | `tests/domain/` |
| application | Casos de uso con puertos falsos en memoria | `tests/application/` (`fakes.py`) |
| infrastructure | Repositorios contra SQLite; PostgreSQL opcional | `tests/test_infrastructure_db.py`, `test_module_repositories.py`, `test_postgres_integration.py` |
| interface | `TestClient` con la app completa: códigos HTTP, forma de errores, roles, 422 frente a 400, 501 | `tests/test_auth.py`, `test_settings_api.py`, `test_modules.py` |
| contrato | Las rutas coinciden con `endpoints.md`; OpenAPI al día | `tests/test_contract.py`, `tests/test_openapi.py` |
| arquitectura | domain y application no importan FastAPI, SQLAlchemy, Pydantic ni infrastructure; entre módulos solo `public.py` | `tests/test_architecture.py` |

## 5. Siguientes pasos
1. `customers` y `reports` sobre sus repositorios (ya hechos), para quitar los 501 de las pantallas principales.
   Requiere `prediction` para las alertas.
2. `quotations` (vista previa, emisión con aprobación, conversión); luego `data_imports`, `prediction`, `explanations`
   e `import_planning`.
3. En cada módulo, el orden es: dominio y pruebas, puertos, repositorio, casos de uso y por último la ruta.
