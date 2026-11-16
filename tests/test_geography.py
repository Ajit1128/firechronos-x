"""Synthetic, offline tests for the Panama ADM0 geographic quality check.

The miniature polygon below is NOT an actual boundary of Panama.
No tests use NASA data, and no network connection is required.
"""
import hashlib
import json

import pandas as pd
import pytest

from scripts.audit_panama_geography import audit, load_boundary


def synthetic_boundary(tmp_path):
    path = tmp_path / "synthetic_adm0.geojson"
    # Deliberately artificial square, not a real Panama boundary.
    feature = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature", "properties": {"synthetic": True},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[-81, 8], [-80, 8], [-80, 9], [-81, 9], [-81, 8]]],
            },
        }],
    }
    path.write_text(json.dumps(feature), encoding="utf-8")
    return path


def sample_csv(path, latitude=(8.5, 8.5, 8.0), longitude=(-80.5, -82.0, -81.0)):
    pd.DataFrame({
        "sensor": ["MODIS", "VIIRS_SNPP", "VIIRS_SNPP"],
        "source_file": ["SYNTHETIC_MODIS.csv", "SYNTHETIC_VIIRS.csv", "SYNTHETIC_VIIRS.csv"],
        "source_row": [2, 2, 3],
        "latitude": latitude, "longitude": longitude,
        "type_raw": ["0", "3", "0"],
    }).to_csv(path, index=False)


def test_cached_boundary_sha256_and_no_network(tmp_path):
    boundary = synthetic_boundary(tmp_path)
    _, metadata = load_boundary(boundary)
    assert metadata["load_method"] == "cached"
    assert metadata["geojson_sha256"] == hashlib.sha256(boundary.read_bytes()).hexdigest()


def test_audit_inside_outside_boundary_and_source_rows(tmp_path):
    boundary = synthetic_boundary(tmp_path)
    input_csv = tmp_path / "detections_SYNTHETIC.csv"
    sample_csv(input_csv)
    original = input_csv.read_bytes()
    output_dir = tmp_path / "outputs"
    report = audit(input_csv, output_dir, boundary)

    assert report["row_count"] == 3
    assert report["count_inside_admin0_land"] == 2  # Includes border point (covers).
    assert report["count_outside_admin0_land"] == 1
    flags = pd.read_csv(output_dir / "geospatial_flags.csv")
    assert flags["inside_panama_adm0_land"].tolist() == [True, False, True]
    assert flags["source_row"].tolist() == [2, 2, 3]
    assert flags["type_raw"].astype(str).tolist() == ["0", "3", "0"]
    assert input_csv.read_bytes() == original
    saved = json.loads((output_dir / "geospatial_audit.json").read_text(encoding="utf-8"))
    assert saved["input_sha256"] == hashlib.sha256(original).hexdigest()


def test_rejects_invalid_coordinates_without_outputs(tmp_path):
    boundary = synthetic_boundary(tmp_path)
    input_csv = tmp_path / "bad_SYNTHETIC.csv"
    sample_csv(input_csv, latitude=(8.5, 8.5, 95.0))
    output_dir = tmp_path / "outputs"
    with pytest.raises(ValueError, match="coordenadas invalidas"):
        audit(input_csv, output_dir, boundary)
    assert not output_dir.exists()


def test_rejects_missing_source_column(tmp_path):
    boundary = synthetic_boundary(tmp_path)
    input_csv = tmp_path / "missing_SYNTHETIC.csv"
    sample_csv(input_csv)
    frame = pd.read_csv(input_csv).drop(columns=["source_row"])
    frame.to_csv(input_csv, index=False)
    with pytest.raises(ValueError, match="Faltan columnas"):
        audit(input_csv, tmp_path / "outputs", boundary)
