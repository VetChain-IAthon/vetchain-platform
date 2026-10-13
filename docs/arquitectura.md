# Arquitectura del backend

```
Navegador ──► Web (Vercel) ──► API (Render) ──► Base de datos (Neon)
                                  │
                                  └──► Gemini API (solo cifras agregadas)
```

La API es un monolito modular: un solo servicio con módulos separados por carpeta.

| Módulo | Ruta | Qué hace | Usa a |
|---|---|---|---|
| auth | `/api/auth` | Usuarios, login y roles | — |
| customers | `/api/customers` | Alertas de clientes dormidos y registro de contactos | prediction, explanations |
| explanations | `/api/explanations` | Texto breve que explica por qué se alerta un cliente | — (llama a Gemini) |
| pricing | `/api/pricing` | Niveles de cliente y reglas de descuento | — |
| quotes | `/api/quotes` | Cotizaciones con reglas de descuento | pricing |
| prediction | `/api/prediction` | Probabilidad de recompra con el modelo XGBoost | — |
| reports | `/api/reports` | KPIs y reportes (ventas, clientes, stock, cobranza, vendedores) | — |
| planning | `/api/planning` | Planificación de importación | prediction |
| data_import | `/api/data-import` | Importar los CSV de Mederi | — |

Flujo de una alerta: customers pide la probabilidad a prediction, luego pide el texto a explanations
(enviando solo cifras agregadas) y devuelve la alerta completa.
