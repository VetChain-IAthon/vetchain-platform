"""Entrena el modelo de recompra (XGBoost) y guarda models/model.json.

PENDIENTE: implementar. Pasos sugeridos:
1. Armar una fila por cliente y fecha de corte: días desde la última compra, frecuencia, monto, familias.
2. Etiqueta: 1 si el cliente compró en los siguientes N días, 0 si no.
3. Separar por fecha (entrenar con lo antiguo, probar con lo reciente).
4. Entrenar XGBoost y guardar con model.save_model("models/model.json").
Referencia: AUC 0.82 con boosting; 0.80 con regresión logística.
"""


def main() -> None:
    raise NotImplementedError("Pendiente: ver el docstring de este archivo.")


if __name__ == "__main__":
    main()
