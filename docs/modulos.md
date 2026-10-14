# Módulos: qué debe hacer cada uno

Roles: `manager` (gerencia) y `salesperson` (vendedor). El vendedor solo opera sobre su cartera.
Detalle de entidades, puertos y casos de uso en [`capas.md`](capas.md), sección 4.

Estado actual: `auth` funciona con login y `/me`, todavía con la estructura plana y las rutas anteriores.
Los demás módulos son solo esqueleto.

Orden sugerido: auth → data_imports → settings → prediction → customers → explanations → quotations → reports → import_planning.

## auth
Sesión (`POST /sessions`), perfil propio (`GET/PATCH /me`) y gestión de usuarios (`/users`, solo `manager`).
Un `salesperson` siempre tiene `salesperson_code`.

## data_imports
Cargar los 7 CSV (sin encabezados) en dos pasos: validar y dejar en espera (`staged`), luego confirmar o cancelar.
Reportar errores por línea. Confirmar actualiza e inserta, nunca borra. Cada carga declara su origen
(`real`, `synthetic`, `simulated`). Script de apoyo: `scripts/load_csv.py`.

## settings
IGV, días de vigencia de la cotización, margen mínimo, rebaja en promociones, niveles A/B/C (descuento máximo,
margen, días de crédito) y umbrales de monto para clasificar a los clientes en B y A.

## prediction
Cargar `models/model.json` y calcular la probabilidad de recompra por cliente. Sin modelo cargado se lanza un
error claro; no se inventan valores. También pronostica la demanda mensual por producto.
Entrenamiento en `scripts/train_model.py`. Referencia de calidad: AUC 0.82; precisión ~84 % en el 10 % superior.

## customers
Lista y ficha de clientes, historial de pedidos, productos que compra, condiciones comerciales, contactos y enlace
de WhatsApp (`wa.me`, sin API). Alertas diarias ordenadas por dinero en juego, con su resumen y su explicación.

## explanations
Explicar una alerta con Gemini usando solo `AggregatedFigures`. Si no hay clave o falla la llamada, devolver un texto
de reserva. Prompt en `prompts/alert_explanation.md`. En "Pregúntale a tus datos", Gemini solo traduce la pregunta a una
consulta permitida; `PrivacyGuard` rechaza cualquier cosa que identifique a un cliente.

## quotations
Buscar productos con precio de referencia (último precio pagado), vista previa sin guardar y emisión.
Pide aprobación si el descuento supera el máximo del nivel o si el margen baja del mínimo. Sin costos, el margen es
nulo con aviso `no_cost_data`. Una cotización emitida no se edita; pasa a `converted` o `expired` cuando se cargan pedidos.

## reports
Panel gerencial, KPIs, reportes de ventas, clientes, stock, cobranza y vendedores, y el embudo de alertas.
Toda cifra lleva `data_origin`. La antigüedad de la deuda se estima con los días de crédito del nivel (`estimated`).

## import_planning
Sugerencia de compra por producto con cantidad y fecha límite. Las decisiones (aprobar, rechazar o volver a pendiente)
se pueden deshacer. Solo la demanda mensual es real; el resto es `simulated` hasta tener stock y costos validados.
