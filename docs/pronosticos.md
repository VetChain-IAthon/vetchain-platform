# Pronóstico por producto

`GET /api/v1/prediction/forecasts` compara el modelo predictivo (`predictive_model`) y el promedio móvil de seis meses para el mismo producto, escenario y horizonte. Requiere sesión de gerencia. Parámetros: `product_id`, `scenario=A|B`, `horizon=1|3` y `cutoff=AAAA-MM` opcional. Si se omite el corte, se usa el mes anterior al mes del pedido válido más reciente. La salida de tres meses es una **cantidad acumulada**, no tres pronósticos mensuales.

`POST /api/v1/prediction/forecasts/explanation` acepta los mismos parámetros en JSON. Gemini redacta únicamente sobre escenario, corte, horizonte y dos cantidades agregadas; no cambia las cifras ni recibe nombres o identificadores de clientes. La respuesta identifica `source=gemini` cuando la API respondió y `source=fallback` cuando se empleó el texto de reserva.

## Modelo predictivo: mezcla

`predictive_model` es el promedio simple de tres componentes: Extra Trees (`extra_trees`), Gradient Boosting con pérdida
Poisson y el promedio móvil de seis meses. El Gradient Boosting usa las 12 variables de Extra Trees más rezagos de 4 a 11
meses, meses sin pedidos y máximo de los últimos 12, tendencia (promedio 3m − 12m), estacionalidad (rezago 12 − promedio 12m)
y meses desde el último pedido; todas con meses anteriores al primer mes pronosticado. Si `FORECAST_MODELS_DIR` no tiene
`boosting_{A|B}_{1|3}m`, `predictive_model` es igual a Extra Trees.

Con el protocolo de la etapa 4 (elegir con 2024, medir en 2025, mismas filas), WAPE promedio de los cuatro casos:

| Método | 2024 | 2025 | Sesgo 2024 / 2025 |
|---|---|---|---|
| Extra Trees | 47.7 % | 27.6 % | +14.3 % / +1.7 % |
| Promedio móvil 6m | 45.1 % | 29.5 % | +4.2 % / +0.9 % |
| Mezcla | 43.9 % | 27.0 % | +2.8 % / −3.9 % |

La mezcla tuvo menos error que los otros dos en los 8 casos (A/B, 1/3 meses, 2024/2025). La elección consideró 2025, que ya se
había examinado: hay que confirmarla con meses nuevos. El código está en el paquete privado (`vetchain_forecast/mezcla.py`,
`train_export_mezcla.py`); la versión de producción se entrena con objetivos hasta diciembre de 2025.

## Datos de entrada

El cálculo consulta `orders` y `order_lines` en la base de datos. Incluye pedidos con estado `T` o `A` y líneas con cantidad positiva. El escenario **A** suma toda esa cantidad solicitada; **B** incluye solo líneas con precio unitario positivo. Se completan con cero los meses sin pedidos desde el primer mes válido de cada producto. Se requieren al menos doce meses anteriores al primer mes pronosticado. Las variables `lag_1/2/3/6/12`, promedios de 3/6/12 meses y desviación de 3 meses se calculan solo con meses anteriores.

La equivalencia de ambas series y de todas las variables se contrastó con las 6 464 filas de cada dataset privado V5. Los casos retrospectivos y una muestra adicional de veinte productos por escenario/horizonte reprodujeron las predicciones del modelo exportado. Estos datasets y los artefactos no se copian al repositorio.

## Artefactos privados

Configura `FORECAST_MODELS_DIR`; en local, `models/forecast/` (ignorada por git, nunca se sube). El directorio debe contener `extratrees_A_1m`, `A_3m`, `B_1m` y `B_3m`, cada uno con archivos `.joblib` y `.json`; para la mezcla, también `boosting_*` con los mismos sufijos. Solo se cargan artefactos de origen confiable. La metadata declara scikit-learn 1.8.0 y pandas 2.2.3; esas versiones están declaradas en `requirements.txt`. Si faltan los archivos o no coinciden con la metadata, la API responde 503.

En producción, los artefactos viven en el repositorio **privado** `VetChain-IAthon/vetchain-models`. El build de Render ejecuta `python -m scripts.fetch_forecast_models`, que los descarga en `FORECAST_MODELS_DIR` (`models/forecast`) con `FORECAST_MODELS_TOKEN`, un token de solo lectura de ese repositorio. Sin token, el build sigue y el pronóstico responde 503. Para actualizar el modelo: reemplazar los archivos en ese repo y volver a desplegar. El repositorio y el frontend no contienen modelos ni CSV de Mederi. Una variable de entorno con una ruta local de desarrollo no sube los artefactos al servidor.

## Interpretación

Las cifras son estimaciones de cantidades solicitadas en pedidos, no ventas facturadas ni órdenes de importación. El resultado de Extra Trees entrenado hasta diciembre de 2024 es experimental: la metadata identifica la evaluación retrospectiva de 2025 como exploratoria y no como un holdout intacto. No se presenta un método como superior para todos los períodos. Gemini no participa en este cálculo.
