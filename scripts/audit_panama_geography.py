"""FireChronos X: land-boundary audit for normalized NASA FIRMS observations.

This is a scientific QC diagnostic, NOT an assertion that every detection
outside the administrative land polygon is erroneous, and NOT harmonization.

Data source: geoBoundaries PAN ADM0, gbOpen (2022 boundary; public domain
for the PAN record). The pinned 9469f09 release URL is held constant so that
later API updates will not silently alter the land boundary. Cite the source
when publishing the result.

Requires: pandas, shapely. Uses only stdlib for download/JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.prepared import prep

BOUNDARY_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
    "releaseData/gbOpen/PAN/ADM0/geoBoundaries-PAN-ADM0.geojson"
)
METADATA_URL = "https://www.geoboundaries.org/api/current/gbOpen/PAN/ADM0/"
MAX_BOUNDARY_BYTES = 12_000_000


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_boundary(cache_path: Path) -> tuple[object, dict]:
    if cache_path.exists():
        raw = cache_path.read_bytes()
        origin = "cached"
    else:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        req = Request(BOUNDARY_URL, headers={"User-Agent": "FireChronosX-research/0.1"})
        try:
            with urlopen(req, timeout=35) as response:
                raw = response.read(MAX_BOUNDARY_BYTES + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(
                "No se pudo obtener el limite de Panama. Comprueba internet o descarga "
                f"el GeoJSON oficial y guardalo en: {cache_path}\nURL: {BOUNDARY_URL}\n{exc}"
            ) from exc
        if len(raw) > MAX_BOUNDARY_BYTES:
            raise ValueError("Archivo geoespacial inesperadamente grande; descarga abortada.")
        # Validate first; only then cache, to avoid saving malformed data.
        origin = "downloaded"
    try:
        feature_collection = json.loads(raw.decode("utf-8-sig"))
        if feature_collection.get("type") == "FeatureCollection":
            geoms = [shape(feature["geometry"]) for feature in feature_collection["features"]]
        elif feature_collection.get("type") == "Feature":
            geoms = [shape(feature_collection["geometry"])]
        else:
            raise ValueError("El archivo no tiene formato GeoJSON Feature/FeatureCollection.")
        if not geoms:
            raise ValueError("El archivo no contiene geometria.")
        geometry = unary_union(geoms)
        if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError("La geometria ADM0 no es un poligono valido.")
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"GeoJSON invalido, no se realizo auditoria: {exc}") from exc
    if origin == "downloaded":
        cache_path.write_bytes(raw)
    metadata = {
        "name": "geoBoundaries gbOpen PAN ADM0",
        "boundary_id": "PAN-ADM0-86535646",
        "boundary_year_represented": "2022",
        "versioned_geometry_url": BOUNDARY_URL,
        "metadata_api_url": METADATA_URL,
        "underlying_source": "The World Factbook - CIA (geoBoundaries metadata)",
        "boundary_license": "Public Domain (PAN ADM0 entry)",
        "geojson_sha256": sha256_bytes(raw),
        "boundary_cache_path": str(cache_path.resolve()),
        "load_method": origin,
        "coordinates": "GeoJSON longitude/latitude, WGS84",
    }
    return geometry, metadata


def audit(input_path: Path, output_dir: Path, boundary_cache: Path) -> dict:
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontro: {input_path}")
    df = pd.read_csv(input_path, dtype={"sensor": "string", "type_raw": "string"}, low_memory=False)
    needed = {"sensor", "latitude", "longitude", "source_file", "source_row"}
    missing = sorted(needed - set(df.columns))
    if missing:
        raise ValueError(f"Faltan columnas en observaciones normalizadas: {missing}")
    if df.empty:
        raise ValueError("No hay observaciones en el archivo procesado.")
    latitude = pd.to_numeric(df["latitude"], errors="coerce")
    longitude = pd.to_numeric(df["longitude"], errors="coerce")
    valid = latitude.between(-90, 90) & longitude.between(-180, 180)
    if not valid.all():
        raise ValueError(f"Hay {int((~valid).sum())} observaciones con coordenadas invalidas; revisar antes de continuar.")
    border, boundary_meta = load_boundary(boundary_cache)
    prepared = prep(border)
    flags = [prepared.covers(Point(float(x), float(y))) for x, y in zip(longitude, latitude)]
    out = df[["sensor", "source_file", "source_row", "latitude", "longitude"]].copy()
    if "type_raw" in df.columns:
        out["type_raw"] = df["type_raw"]
    out["inside_panama_adm0_land"] = flags
    counts = []
    for sensor, group in out.groupby("sensor", dropna=False):
        inside = int(group["inside_panama_adm0_land"].sum())
        counts.append({"sensor": str(sensor), "total": int(len(group)), "inside_adm0_land": inside,
                       "outside_adm0_land": int(len(group) - inside)})
    outside = out.loc[~out["inside_panama_adm0_land"]]
    report = {
        "status": "geographical_land_boundary_check_only_not_full_geolocation_validation",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path.resolve()),
        "input_sha256": sha256_bytes(input_path.read_bytes()),
        "boundary": boundary_meta,
        "row_count": int(len(df)),
        "count_inside_admin0_land": int(sum(flags)),
        "count_outside_admin0_land": int(len(df) - sum(flags)),
        "count_by_sensor": counts,
        "outside_examples_max_10": outside.head(10).to_dict(orient="records"),
        "warnings": [
            "ADM0 es un limite administrativo terrestre, no aguas territoriales ni huellas de pixels.",
            "Un punto fuera de ADM0 no prueba por si solo un error de NASA: puede ser costa, isla, agua o borde.",
            "Una deteccion termica NO equivale a un incendio individual.",
            "No se aplico armonizacion intersensor ni correccion de incertidumbre espacial.",
            "La geometria de referencia representa 2022; el CSV de FIRMS es de marzo de 2024.",
            "No se debe filtrar ni borrar observaciones automaticamente por este indicador.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_dir / "geospatial_flags.csv", index=False)
    (output_dir / "geospatial_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="FireChronos X - Auditar puntos con limite terrestre ADM0 de Panama")
    parser.add_argument("--input", type=Path, required=True, help="detections_normalized.csv")
    parser.add_argument("--output-dir", type=Path, required=True, help="Carpeta local, fuera de Git")
    parser.add_argument("--boundary-cache", type=Path, required=True, help="GeoJSON de limite de Panama cacheado")
    args = parser.parse_args()
    try:
        result = audit(args.input, args.output_dir, args.boundary_cache)
    except (FileNotFoundError, ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f"ERROR: {error}\n")
    print("=== FIRECHRONOS X - Auditoria geoespacial ===")
    print("Total:", result["row_count"])
    for item in result["count_by_sensor"]:
        print(f"{item['sensor']}: dentro ADM0={item['inside_adm0_land']}, fuera ADM0={item['outside_adm0_land']}")
    print("SHA256 del limite:", result["boundary"]["geojson_sha256"])
    print("Salida:", args.output_dir.resolve())
    print("AVISO: ADM0 solo es limite terrestre; no filtrar observaciones automaticamente.")


if __name__ == "__main__":
    main()
