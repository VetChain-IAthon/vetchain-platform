"""Carga los 7 CSV de Defontana (sin encabezados) a la base configurada en DATABASE_URL.

Uso: python -m scripts.load_csv [carpeta]   (por defecto data/)
Nombres oficiales: mederi-1-ventas.csv ... mederi-7-vendedores.csv (también acepta 1_clientes.csv ... 7_vendedores.csv).
Crea las tablas si no existen, hace upsert y nunca borra: se puede repetir sin duplicar.
"""
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.infrastructure.loaders.defontana_csv import SourceReport, load_directory

DEFAULT_DIRECTORY = Path("data")


def print_report(reports: list[SourceReport]) -> None:
    print(f"{'Tabla':<16}{'Archivo':<32}{'Leídas':>8}{'Cargadas':>10}{'Rechazadas':>12}")
    for report in reports:
        print(f"{report.table:<16}{report.file:<32}{report.rows_read:>8}{report.rows_loaded:>10}{report.rows_rejected:>12}")
    for report in reports:
        for reason, count in report.rejected.most_common():
            print(f"  Rechazo  {report.table}: {reason} ({count})")
        for line, reason in report.rejected_samples:
            print(f"           línea {line}: {reason}")
        for warning, count in report.warnings.most_common():
            print(f"  Aviso    {report.table}: {warning} ({count})")


def main() -> None:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIRECTORY
    if not directory.is_dir():
        sys.exit(f"No existe la carpeta {directory}.")
    with SessionLocal() as session:
        reports = load_directory(session, directory)
    print_report(reports)
    if any(report.rows_rejected for report in reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
