"""Inspect downloaded NASA FIRMS CSVs without modifying their contents."""
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
raw = root / "data" / "raw"
files = sorted(raw.rglob("*.csv")) if raw.exists() else []
print("=== FIRECHRONOS X / NASA FIRMS inspector ===")
if not files:
    print("No hay CSV en data/raw. La solicitud NASA aún puede estar procesándose.")
else:
    for file in files:
        print(f"\nArchivo: {file.relative_to(root)}")
        try:
            frame = pd.read_csv(file, nrows=5)
            print("Columnas:", ", ".join(frame.columns))
            print("Muestra (máximo 3 filas):")
            print(frame.head(3).to_string(index=False))
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as exc:
            print(f"ERROR al leer: {exc}")
