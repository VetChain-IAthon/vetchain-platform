# Arquitectura del backend

```
Navegador ──► Web (Vercel) ──► API (Render) ──► Base de datos (Neon)
                                  │
                                  └──► Gemini API (solo cifras agregadas)
```

La API es un **monolito modular**: un solo servicio con módulos separados por carpeta.
Cada módulo se organiza en cuatro capas (domain, application, infrastructure, interface).
Las reglas completas están en [`capas.md`](capas.md).

## Módulos

| Módulo | Qué hace | Recursos que expone (`/api/v1`) | Llama a (por `public.py`) |
|---|---|---|---|
| auth | Usuarios, sesión y roles | `/sessions`, `/me`, `/users` | — |
| customers | Clientes, alertas diarias de clientes dormidos y contactos | `/customers`, `/alerts` | prediction, explanations, settings |
| explanations | Texto con Gemini que explica una alerta; preguntas a los datos | `/insights/questions` | reports |
| settings | IGV, vigencia, margen mínimo, niveles A/B/C y umbrales | `/settings/*` | — |
| quotations | Productos, vista previa y emisión de cotizaciones | `/products`, `/quotation-previews`, `/quotations` | settings, customers |
| prediction | Probabilidad de recompra (XGBoost) y pronóstico de demanda | `/prediction/model` | — |
| reports | Panel gerencial, KPIs y reportes | `/dashboard/*`, `/reports/*` | settings, data_imports |
| import_planning | Sugerencias de importación por producto | `/import-suggestions` | prediction |
| data_imports | Carga de los 7 CSV de Mederi (validar, revisar, confirmar) | `/data-sources`, `/data-imports` | quotations |

`/health` queda fuera de los módulos.

## Flujos principales

- **Alerta diaria.** La tarea `GenerateDailyAlerts` de customers pide probabilidades a prediction y guarda una alerta
  por cliente y día. Cuando alguien abre la explicación, customers arma `AggregatedFigures` (sin nombre ni RUC) y
  se las pasa a explanations, que llama a Gemini o devuelve un texto de reserva.
- **Cotización.** quotations pide a customers las condiciones comerciales del cliente y a settings el IGV, la
  vigencia y el margen mínimo. Calcula los totales y decide si hace falta aprobación.
- **Carga de datos.** data_imports valida el CSV y lo deja en espera (`staged`). Al confirmarlo hace un upsert,
  sin borrar nada. Si la carga es de pedidos, avisa a quotations para marcar las cotizaciones convertidas o vencidas.
- **Pregunta a los datos.** explanations convierte la pregunta en una consulta permitida (`InsightQuery`), reports
  la ejecuta y la respuesta sale de la base, no de Gemini.

## Estado actual

El código todavía está en estructura plana (`router.py`, `service.py`, `schemas.py`, `models.py`) y con nombres
anteriores. Cada módulo se pasa a capas cuando se construye. Ver la sección 8 de [`capas.md`](capas.md).
