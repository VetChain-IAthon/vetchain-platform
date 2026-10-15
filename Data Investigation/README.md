# Data Investigation

Cuadernos de Google Colab usados para preparar los datos de Mederi y entrenar el pronóstico.

| Cuaderno | Qué hace |
|---|---|
| `VetChain_Colab_V4_1_limpieza_y_auditoria.ipynb` | Limpieza y auditoría de los 7 CSV de Mederi, ventas y obsequios a S/ 0.00, panel mensual por producto y variables predictivas sin fuga temporal (base de los datasets V5 del pronóstico). |

Los cuadernos se publican **sin resultados**: las tablas, gráficos y códigos de producto que generan son datos de Mederi y
este repositorio es público. Para verlos, abre el cuaderno en Colab y sube los CSV (`mederi-1-...` a `mederi-7-...`).

El modelo predictivo (mezcla de Extra Trees, Gradient Boosting y promedio móvil) se entrena con el paquete privado
`VetChain_ExtraTrees` (`train_export_mezcla.py`); sus métricas y su uso en la API están en `docs/pronosticos.md`.
Los datasets V5 y los artefactos `.joblib` no se suben a este repositorio.
