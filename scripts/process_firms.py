"""CLI: normalize a pair of genuine NASA FIRMS MODIS and VIIRS S-NPP CSVs."""
import argparse
import json
from pathlib import Path
import sys

# Allows running from project root without having to pip install package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from firechronos.pipeline import FIRMSValidationError, process_pair  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="FIRECHRONOS X: importar y revisar dos CSV NASA FIRMS")
    p.add_argument("--modis", type=Path, required=True, help="CSV original MODIS")
    p.add_argument("--viirs", type=Path, required=True, help="CSV original VIIRS S-NPP")
    p.add_argument("--output", type=Path, default=Path("data/processed"))
    p.add_argument("--start", help="Fecha esperada, YYYY-MM-DD")
    p.add_argument("--end", help="Fecha esperada, YYYY-MM-DD")
    args = p.parse_args()
    try:
        result = process_pair(args.modis, args.viirs, args.output, args.start, args.end)
    except (FIRMSValidationError, FileNotFoundError, ValueError) as exc:
        p.exit(2, f"ERROR: {exc}\n")
    print(json.dumps({"records": result["record_count_by_sensor"], "output": str(args.output)}, indent=2))
    print("AVISO: esto es normalización de esquema, NO armonización científica.")


if __name__ == "__main__":
    main()
