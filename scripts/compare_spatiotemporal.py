"""Exploratory MODIS–VIIRS proximity candidates, NOT validated harmonization.

Nearest MODIS detection for each VIIRS detection, constrained by UTC time and
haversine distance. Not one-to-one; never infer individual fire identity.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088
NEEDED = {"sensor", "latitude", "longitude", "acquired_at_utc", "source_file", "source_row", "type_raw"}
COLUMNS = [
    "viirs_source_file", "viirs_source_row", "viirs_acquired_at_utc",
    "viirs_latitude", "viirs_longitude", "modis_source_file", "modis_source_row",
    "modis_acquired_at_utc", "modis_latitude", "modis_longitude",
    "distance_km", "time_difference_minutes",
]


def haversine_km(lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Great-circle distance between a point and arrays of points."""
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def compare(df: pd.DataFrame, radius_km: float = 1.0, minutes: float = 60.0,
            type_zero_only: bool = True) -> tuple[pd.DataFrame, dict]:
    """Identify nonexclusive *candidate* proximity pairs within chosen thresholds."""
    if radius_km <= 0 or minutes <= 0 or not np.isfinite([radius_km, minutes]).all():
        raise ValueError("radius_km and minutes must be finite positive numbers")
    missing = NEEDED - set(df.columns)
    if missing:
        raise ValueError(f"Missing normalized columns: {sorted(missing)}")
    if not set(df["sensor"].dropna().unique()).issubset({"MODIS", "VIIRS_SNPP"}):
        raise ValueError("Unexpected sensor; expected MODIS and VIIRS_SNPP")
    data = df.copy()
    # Blank, missing, and unclassified values are not assumed to be type 0.
    # Compute audit counts on the ORIGINAL input, before filtering rows.
    types = data["type_raw"].astype("string").fillna("").str.strip()
    type_missing = types.eq("")
    excluded_missing = int(type_missing.sum()) if type_zero_only else 0
    excluded_other = (
        int((~type_missing & types.ne("0")).sum()) if type_zero_only else 0
    )

    if type_zero_only:
        data = data.loc[types.eq("0")].copy()
    for col in ("latitude", "longitude"):
        data[col] = pd.to_numeric(data[col], errors="raise")
    if data[["latitude", "longitude"]].isna().any().any():
        raise ValueError("Missing coordinates")
    if not data["latitude"].between(-90, 90).all() or not data["longitude"].between(-180, 180).all():
        raise ValueError("Out-of-range coordinates")
    data["timestamp"] = pd.to_datetime(data["acquired_at_utc"], utc=True, errors="raise")
    if data["timestamp"].isna().any():
        raise ValueError("Missing UTC timestamp")
    modis = data.loc[data["sensor"].eq("MODIS")].sort_values("timestamp").reset_index(drop=True)
    viirs = data.loc[data["sensor"].eq("VIIRS_SNPP")].reset_index(drop=True)
    ts_modis = modis["timestamp"].dt.as_unit("ns").astype("int64").to_numpy()
    lat_modis = modis["latitude"].to_numpy(dtype=float)
    lon_modis = modis["longitude"].to_numpy(dtype=float)
    time_delta_ns = int(minutes * 60 * 1_000_000_000)
    found = []
    for v in viirs.itertuples(index=False):
        vtime = v.timestamp.value
        left = np.searchsorted(ts_modis, vtime - time_delta_ns, side="left")
        right = np.searchsorted(ts_modis, vtime + time_delta_ns, side="right")
        if left >= right:
            continue
        distances = haversine_km(float(v.latitude), float(v.longitude),
                                 lat_modis[left:right], lon_modis[left:right])
        nearby = np.flatnonzero(distances <= radius_km)
        if not len(nearby):
            continue
        # Choose smallest distance; break ties by smallest temporal difference.
        idx = sorted(nearby, key=lambda j: (distances[j],
                     abs(ts_modis[left + j] - vtime), left + j))[0]
        m = modis.iloc[left + idx]
        found.append({
            "viirs_source_file": v.source_file, "viirs_source_row": v.source_row,
            "viirs_acquired_at_utc": v.acquired_at_utc,
            "viirs_latitude": v.latitude, "viirs_longitude": v.longitude,
            "modis_source_file": m["source_file"], "modis_source_row": m["source_row"],
            "modis_acquired_at_utc": m["acquired_at_utc"],
            "modis_latitude": m["latitude"], "modis_longitude": m["longitude"],
            "distance_km": round(float(distances[idx]), 6),
            "time_difference_minutes": round(float(abs(ts_modis[left + idx] - vtime) / 60_000_000_000), 3),
        })
    pairs = pd.DataFrame(found, columns=COLUMNS)
    report = {
        "method": "exploratory_nearest_spatiotemporal_proximity_not_harmonization",
        "radius_km": radius_km,
        "time_window_minutes": minutes,
        "type_zero_only": type_zero_only,
        "type_missing_in_input": int(type_missing.sum()),
        "type_missing_by_sensor": {
            "MODIS": int((df["sensor"].eq("MODIS") & type_missing).sum()),
            "VIIRS_SNPP": int((df["sensor"].eq("VIIRS_SNPP") & type_missing).sum()),
        },
        "excluded_missing_type": excluded_missing,
        "excluded_other_type": excluded_other,
        "input_count": len(df),
        "selected_modis": len(modis),
        "selected_viirs": len(viirs),
        "viirs_rows_with_candidate": len(pairs),
        "modis_rows_selected_by_candidates": int(len(pairs[["modis_source_file", "modis_source_row"]].drop_duplicates())) if len(pairs) else 0,
        "caveats": [
            "Proximity is NOT proof of the same fire or a validated sensor match.",
            "Not one-to-one: several VIIRS rows may reference the same MODIS detection.",
            "Unmatched VIIRS does NOT imply missing MODIS coverage or sensor failure.",
            "Pixel footprints, orbit times, confidence, observation biases and uncertainty are not calibrated.",
            "Thresholds are exploratory and must be assessed with sensitivity analysis.",
            "Default type=0 mode excludes missing and other classifications; --all-types includes them.",
        ],
    }
    return pairs, report


def main() -> None:
    ap = argparse.ArgumentParser(description="FireChronos X: exploratory sensor proximity")
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--radius-km", default=1.0, type=float)
    ap.add_argument("--minutes", default=60.0, type=float)
    ap.add_argument("--all-types", action="store_true", help="Include non-vegetation thermal anomalies")
    args = ap.parse_args()
    try:
        data = pd.read_csv(args.input, dtype="string", keep_default_na=False)
        pairs, report = compare(data, args.radius_km, args.minutes, not args.all_types)
    except (ValueError, OSError, pd.errors.ParserError) as e:
        ap.exit(2, f"ERROR: {e}\n")
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    report["input_sha256"] = digest
    report["input_file"] = args.input.name
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(args.output_dir / "proximity_candidates.csv", index=False)
    (args.output_dir / "proximity_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "input_count", "selected_modis", "selected_viirs", "viirs_rows_with_candidate",
        "modis_rows_selected_by_candidates", "radius_km", "time_window_minutes")}, indent=2))
    print("AVISO: proximidad exploratoria, NO armonización ni identificación de incendios.")


if __name__ == "__main__":
    main()
