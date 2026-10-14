from enum import StrEnum


class DataOrigin(StrEnum):
    """De dónde sale un dato, para que la web muestre la etiqueta."""

    REAL = "real"
    SYNTHETIC = "synthetic"
    ESTIMATED = "estimated"
    SIMULATED = "simulated"

    @staticmethod
    def least_reliable(origins: "list[DataOrigin] | set[DataOrigin] | tuple[DataOrigin, ...]") -> "DataOrigin":
        """Origen que se muestra cuando una respuesta mezcla varios: el menos confiable."""
        if not origins:
            raise ValueError("Se necesita al menos un origen.")
        return max(origins, key=_RELIABILITY_RANK.__getitem__)


_RELIABILITY_RANK = {
    DataOrigin.REAL: 0,
    DataOrigin.ESTIMATED: 1,
    DataOrigin.SYNTHETIC: 2,
    DataOrigin.SIMULATED: 3,
}
