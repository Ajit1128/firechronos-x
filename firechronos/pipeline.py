"""FIRMS CSV inspection, provenance-preserving normalization and daily tallies.

Only normalizes schema. It does NOT calibrate, harmonize, or convert
thermal detections into independent fire incidents.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "latitude", "longitude", "acq_date",
    "acq_time", "satellite", "version"
}

ALLOWED_SENSORS = {"MODIS", "VIIRS_SNPP"}
# FIRMS version denotes collection AND processing stream (NASA FIRMS attribute tables).
# Fail closed on unknown collections, rather than fabricating provenance labels.
EXPECTED_COLLECTIONS = {
    "MODIS": ("6.1", "modis-c6.1"),
    "VIIRS_SNPP": ("2.0", "suomi-viirs-c2"),
}
PROCESSING_SUFFIXES = {
    "": "standard",
    "NRT": "near_real_time",
    "RT": "real_time",
    "URT": "ultra_real_time",
}
NORMALIZED_COLUMNS = [
    "sensor", "source_product", "source_processing", "source_file", "source_sha256", "source_row",
    "latitude", "longitude", "acq_date", "acq_time", "acquired_at_utc",
    "satellite", "instrument", "version", "confidence_raw", "confidence_scale","type_raw",
    "frp_raw", "frp_mw", "daynight", "scan_km", "track_km",
    "brightness_k", "bright_t31_k", "bright_ti4_k", "bright_ti5_k",
]


class FIRMSValidationError(ValueError):
    """Indicates that CSV input does not meet the declared format contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_column(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return df[name].astype("string").fillna("").str.strip()
    return pd.Series("", index=df.index, dtype="string")


def _numeric_column(df: pd.DataFrame, name: str) -> pd.Series:
    return pd.to_numeric(_text_column(df, name).replace("", pd.NA), errors="coerce")


def _assert_valid_coordinates(df: pd.DataFrame, latitude: pd.Series, longitude: pd.Series) -> None:
    bad = latitude.isna() | longitude.isna() | ~latitude.between(-90, 90) | ~longitude.between(-180, 180)
    if bad.any():
        rows = (df.index[bad][:5] + 2).tolist()  # first CSV data row is line 2
        raise FIRMSValidationError(f"Coordenadas inválidas en líneas CSV: {rows}. No se descartaron filas.")


def _parse_times(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    dates = _text_column(df, "acq_date")
    # FIRMS times can appear without their leading zeros (e.g. 3 -> 0003 UTC).
    raw_times = _text_column(df, "acq_time")
    times = raw_times.str.zfill(4)
    hh = pd.to_numeric(times.str.slice(0, 2), errors="coerce")
    mm = pd.to_numeric(times.str.slice(2, 4), errors="coerce")
    valid_time = raw_times.str.fullmatch(r"\d{1,4}").fillna(False) & hh.between(0, 23) & mm.between(0, 59)
    parsed_date = pd.to_datetime(dates, format="%Y-%m-%d", errors="coerce", utc=True)
    bad = parsed_date.isna() | ~valid_time
    if bad.any():
        rows = (df.index[bad][:5] + 2).tolist()
        raise FIRMSValidationError(f"Fecha u hora UTC inválida en líneas CSV: {rows}.")
    acquired = pd.to_datetime(dates + " " + times, format="%Y-%m-%d %H%M", utc=True, errors="raise")
    return dates, times, acquired


def _validate_identity_and_version(df: pd.DataFrame, sensor: str) -> tuple[pd.Series, pd.Series]:
    """Require FIRMS CSV metadata consistent with the declared satellite/product.

    Confirms internal CSV consistency, NOT independent NASA authenticity.
    """
    
    
    # Validate instrument only when supplied by the CSV.
    # MODIS archives may omit this column.
    
    # Validate instrument only when supplied by the CSV.
    if "instrument" in df.columns:
        allowed_instruments = (
            {"MODIS"} if sensor == "MODIS"
            else {"VIIRS", "SNPP"}
        )

        instruments = _text_column(df, "instrument").str.upper()
        bad_instrument = ~instruments.isin(allowed_instruments)

        if bad_instrument.any():
            raise FIRMSValidationError(
                f"Incompatibilidad de sensor declarado {sensor}: "
                f"instrument encontrado "
                f"{sorted(instruments[bad_instrument].unique().tolist())}."
            )

    # NASA FIRMS: T=Terra, A=Aqua, N=Suomi NPP. Do not label NOAA-20/21 as S-NPP.

    allowed_satellites = (
        {"T", "A", "TERRA", "AQUA"}
        if sensor == "MODIS"
        else {"N", "SUOMI NPP", "SUOMI-NPP", "S-NPP", "SNPP"}
    )

    satellites = _text_column(df, "satellite").str.upper()
    bad_satellite = ~satellites.isin(allowed_satellites)
    if bad_satellite.any():
        raise FIRMSValidationError(
            f"Satélite incompatible con {sensor}: "
            f"{sorted(satellites[bad_satellite].unique().tolist())}."
        )

    expected_version, product_label = EXPECTED_COLLECTIONS[sensor]
    versions = _text_column(df, "version").str.upper()
    products = pd.Series(index=df.index, dtype="string")
    processing = pd.Series(index=df.index, dtype="string")
    for suffix, processing_name in PROCESSING_SUFFIXES.items():
        matching = versions == f"{expected_version}{suffix}".upper()
        products.loc[matching] = product_label + (f"-{suffix.lower()}" if suffix else "")
        processing.loc[matching] = processing_name


    # Identificador observado en el archivo histórico MODIS C6.1.
    # Se conserva la versión original y no se presupone el
    # tipo de procesamiento a partir del sufijo ".03".
    if sensor == "MODIS":
        archive_version = versions.eq("61.03")
        products.loc[archive_version] = product_label
        processing.loc[archive_version] = "unverified_archive"


    if sensor == "VIIRS_SNPP":
        archive_version = versions.eq("2")
        products.loc[archive_version] = product_label
        processing.loc[archive_version] = "unverified_archive"



    invalid = processing.isna()
    if invalid.any():
        rows = (df.index[invalid][:5] + 2).tolist()
        values = sorted(versions[invalid].unique().tolist())
        raise FIRMSValidationError(
            f"Versión/colección incompatible con {sensor} en líneas {rows}: "
            f"{values}. Se esperaba {expected_version} (+ NRT/RT/URT opcional)."
        )
    return products, processing


def load_firms_csv(path: Path | str, sensor: str) -> tuple[pd.DataFrame, dict]:
    """Read a sensor-declared FIRMS CSV, validate basic schema, preserve provenance.

    Sensor is supplied explicitly: never inferred from an unreliable filename.
    Returns normalized rows and a source metadata dict.
    """
    if sensor not in ALLOWED_SENSORS:
        raise ValueError(f"Sensor inválido {sensor!r}; usar MODIS o VIIRS_SNPP.")
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el CSV: {path}")
    if path.suffix.lower() != ".csv":
        raise FIRMSValidationError("Debes extraer el ZIP de NASA y seleccionar un archivo .csv.")
    try:
        # Read as text first to retain original confidence and acquisition HHMM.
        df = pd.read_csv(path, dtype="string", keep_default_na=False, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeError) as exc:
        raise FIRMSValidationError(f"No se pudo leer el CSV {path.name}: {exc}") from exc
    df.columns = df.columns.str.strip().str.lower()
    if df.columns.duplicated().any():
        raise FIRMSValidationError(f"Columnas repetidas en {path.name}.")
    missing = sorted(REQUIRED_COLUMNS - set(df.columns))
    if missing:
        raise FIRMSValidationError(f"Faltan columnas obligatorias en {path.name}: {missing}")

    
    if sensor == "VIIRS_SNPP" and "instrument" not in df.columns:
        raise FIRMSValidationError(
            "Falta columna instrument para VIIRS_SNPP."
        )

    if df.empty:
        raise FIRMSValidationError(f"CSV sin filas: {path.name}")
    source_products, source_processing = _validate_identity_and_version(df, sensor)
    lat = _numeric_column(df, "latitude")
    lon = _numeric_column(df, "longitude")
    _assert_valid_coordinates(df, lat, lon)
    dates, times, acquired = _parse_times(df)
    frp_raw = _text_column(df, "frp")
    frp = _numeric_column(df, "frp")
    invalid_frp = (frp_raw != "") & frp.isna()
    # Keep the invalid raw string for audit; do not silently turn it into a valid value.
    sha256 = _sha256(path)
    normalized = pd.DataFrame(index=df.index)
    normalized["sensor"] = sensor
    normalized["source_product"] = source_products
    normalized["source_processing"] = source_processing
    normalized["source_file"] = path.name
    normalized["source_sha256"] = sha256
    normalized["source_row"] = df.index + 2
    normalized["latitude"] = lat
    normalized["longitude"] = lon
    normalized["acq_date"] = dates
    normalized["acq_time"] = times
    normalized["acquired_at_utc"] = acquired.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    for col in ("satellite", "instrument", "version", "daynight"):
        normalized[col] = _text_column(df, col)
    normalized["confidence_raw"] = _text_column(df, "confidence")
    normalized["type_raw"] = _text_column(df, "type")
    normalized["confidence_scale"] = "numeric_0_100" if sensor == "MODIS" else "categorical_low_nominal_high"
    normalized["frp_raw"] = frp_raw
    normalized["frp_mw"] = frp
    for col in ("scan", "track"):
        normalized[f"{col}_km"] = _numeric_column(df, col)
    for col in ("brightness", "bright_t31", "bright_ti4", "bright_ti5"):
        normalized[f"{col}_k"] = _numeric_column(df, col)
    normalized = normalized[NORMALIZED_COLUMNS]
    details = {
        "sensor": sensor,
        "source_products": sorted(source_products.unique().tolist()),
        "source_processing": sorted(source_processing.unique().tolist()),
        "file": path.name,
        "sha256": sha256,
        "records": int(len(df)),
        "original_columns": list(df.columns),
        "instrument_column_present": "instrument" in df.columns,
        "missing_frp": int((frp_raw == "").sum()),
        "invalid_numeric_frp": int(invalid_frp.sum()),
        "raw_file_unchanged": True,
    }
    return normalized, details


def process_pair(modis: Path | str, viirs: Path | str, output_dir: Path | str,
                 start: str | None = None, end: str | None = None) -> dict:
    """Write reproducible normalized observations, counts, and audit metadata."""
    if Path(modis).resolve() == Path(viirs).resolve():
        raise FIRMSValidationError("MODIS y VIIRS deben ser archivos diferentes.")
    m, m_meta = load_firms_csv(modis, "MODIS")
    v, v_meta = load_firms_csv(viirs, "VIIRS_SNPP")
    observations = pd.concat([m.astype(object), v.astype(object)], ignore_index=True)
    if start is not None or end is not None:
        if not (start and end):
            raise FIRMSValidationError("Para validar el intervalo se requieren --start y --end.")
        try:
            a = pd.Timestamp(start).strftime("%Y-%m-%d")
            b = pd.Timestamp(end).strftime("%Y-%m-%d")
        except ValueError as exc:
            raise FIRMSValidationError(f"Fechas esperadas inválidas: {exc}") from exc
        if a > b:
            raise FIRMSValidationError("La fecha de inicio es mayor que la final.")
        invalid = ~observations["acq_date"].between(a, b)
        if invalid.any():
            raise FIRMSValidationError(
                f"{int(invalid.sum())} registros fuera del intervalo esperado {a} a {b}; "
                "revisar que los archivos correspondan a la descarga solicitada."
            )
    # Only dates with actual detections appear. Absent dates are NOT assumed zero activity.
    daily = (
        observations.groupby(["acq_date", "sensor"], dropna=False)
        .size().rename("detection_count").reset_index()
        .sort_values(["acq_date", "sensor"])
    )
    # Output folder is created only after both datasets have passed basic validation.
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    observations.to_csv(output_dir / "detections_normalized.csv", index=False)
    daily.to_csv(output_dir / "daily_detection_counts.csv", index=False)
    report = {
        "status": "schema_normalized_not_scientifically_harmonized",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "record_count_total": int(len(observations)),
        "record_count_by_sensor": {"MODIS": int(len(m)), "VIIRS_SNPP": int(len(v))},
        "sources": [m_meta, v_meta],
        "caveats": [
            "Cada fila es una detección térmica, no un incendio individual.",
            "Conteos de MODIS y VIIRS no son directamente equivalentes.",
            "Los días sin detecciones no representan necesariamente cobertura completa ni cero incendios.",
            "La confianza MODIS (numérica) y VIIRS (categórica) no son intercambiables.",
            "No se aplicó calibración, emparejamiento espacio-temporal ni armonización validada.",
            "La selección geográfica Panamá se asume hecha en el portal NASA; aquí solo se validan rangos globales.",
        ],
    }
    (output_dir / "quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report
