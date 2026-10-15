# Pronóstico por producto

`GET /api/v1/prediction/forecasts` compara Extra Trees y el promedio móvil de seis meses para el mismo producto, escenario y horizonte. Requiere sesión de gerencia. Parámetros: `product_id`, `scenario=A|B`, `horizon=1|3` y `cutoff=AAAA-MM` opcional. Si se omite el corte, se usa el mes anterior al mes del pedido válido más reciente. La salida de tres meses es una **cantidad acumulada**, no tres pronósticos mensuales.

`POST /api/v1/prediction/forecasts/explanation` acepta los mismos parámetros en JSON. Gemini redacta únicamente sobre escenario, corte, horizonte y dos cantidades agregadas; no cambia las cifras ni recibe nombres o identificadores de clientes. La respuesta identifica `source=gemini` cuando la API respondió y `source=fallback` cuando se empleó el texto de reserva.

## Datos de entrada

El cálculo consulta `orders` y `order_lines` en la base de datos. Incluye pedidos con estado `T` o `A` y líneas con cantidad positiva. El escenario **A** suma toda esa cantidad solicitada; **B** incluye solo líneas con precio unitario positivo. Se completan con cero los meses sin pedidos desde el primer mes válido de cada producto. Se requieren al menos doce meses anteriores al primer mes pronosticado. Las variables `lag_1/2/3/6/12`, promedios de 3/6/12 meses y desviación de 3 meses se calculan solo con meses anteriores.

La equivalencia de ambas series y de todas las variables se contrastó con las 6 464 filas de cada dataset privado V5. Los casos retrospectivos y una muestra adicional de veinte productos por escenario/horizonte reprodujeron las predicciones del modelo exportado. Estos datasets y los artefactos no se copian al repositorio.

## Artefactos privados

Configura `FORECAST_MODELS_DIR` fuera del repositorio. El directorio debe contener `extratrees_A_1m`, `A_3m`, `B_1m` y `B_3m`, cada uno con archivos `.joblib` y `.json`. Solo se cargan artefactos de origen confiable. La metadata declara scikit-learn 1.8.0 y pandas 2.2.3; esas versiones están declaradas en `requirements.txt`. Si faltan los archivos o no coinciden con la metadata, la API responde 503.

En producción, provisiona esos archivos mediante un mecanismo privado del servidor antes de iniciar la API y apunta `FORECAST_MODELS_DIR` a esa ubicación. El repositorio y el frontend no contienen modelos ni CSV de Mederi. Una variable de entorno con una ruta local de desarrollo no sube los artefactos al servidor.

## Interpretación

Las cifras son estimaciones de cantidades solicitadas en pedidos, no ventas facturadas ni órdenes de importación. El resultado de Extra Trees entrenado hasta diciembre de 2024 es experimental: la metadata identifica la evaluación retrospectiva de 2025 como exploratoria y no como un holdout intacto. No se presenta un método como superior para todos los períodos. Gemini no participa en este cálculo.
