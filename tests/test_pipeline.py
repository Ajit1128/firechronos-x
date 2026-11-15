"""All tests use SYNTHETIC fixtures, never fabricated NASA observations."""
from pathlib import Path
import json

import pandas as pd
import pytest

from firechronos.pipeline import FIRMSValidationError, load_firms_csv, process_pair

FIX = Path(__file__).parent / "fixtures"
M = FIX / "modis_SYNTHETIC.csv"
V = FIX / "viirs_SYNTHETIC.csv"


def test_preserves_distinct_confidence_scales_and_utc_time():
    modis, m_meta = load_firms_csv(M, "MODIS")
    viirs, v_meta = load_firms_csv(V, "VIIRS_SNPP")
    assert m_meta["records"] == v_meta["records"] == 2
    assert modis.loc[0, "confidence_raw"] == "75"
    assert modis.loc[0, "confidence_scale"] == "numeric_0_100"
    assert viirs.loc[0, "confidence_raw"] == "nominal"
    assert viirs.loc[0, "confidence_scale"] == "categorical_low_nominal_high"
    assert viirs.loc[0, "acquired_at_utc"] == "2024-03-01T00:25:00Z"
    assert modis.loc[0, "acquired_at_utc"] == "2024-03-01T00:23:00Z"
    assert len(modis.loc[0, "source_sha256"]) == 64


def test_process_writes_artifacts_with_real_provenance_fields(tmp_path):
    report = process_pair(M, V, tmp_path, start="2024-03-01", end="2024-03-31")
    assert report["record_count_total"] == 4
    assert (tmp_path / "quality_report.json").exists()
    norm = pd.read_csv(tmp_path / "detections_normalized.csv")
    assert len(norm) == 4
    assert set(norm["sensor"]) == {"MODIS", "VIIRS_SNPP"}
    daily = pd.read_csv(tmp_path / "daily_detection_counts.csv")
    assert daily["detection_count"].sum() == 4
    assert json.loads((tmp_path / "quality_report.json").read_text(encoding="utf-8"))["status"] == "schema_normalized_not_scientifically_harmonized"


def test_fails_on_invalid_coordinates_and_does_not_drop_silently(tmp_path):
    df = pd.read_csv(M)
    df.loc[0, "latitude"] = 200
    path = tmp_path / "invalid.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Coordenadas inválidas"):
        load_firms_csv(path, "MODIS")


def test_fails_on_invalid_time(tmp_path):
    df = pd.read_csv(V, dtype=str)
    df.loc[0, "acq_time"] = "2465"
    path = tmp_path / "invalid.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Fecha u hora"):
        load_firms_csv(path, "VIIRS_SNPP")


def test_fails_on_mismatched_instrument():
    with pytest.raises(FIRMSValidationError, match="Incompatibilidad"):
        load_firms_csv(M, "VIIRS_SNPP")


def test_fails_on_wrong_period_without_output(tmp_path):
    out = tmp_path / "results"
    with pytest.raises(FIRMSValidationError, match="fuera del intervalo"):
        process_pair(M, V, out, "2025-01-01", "2025-01-31")
    assert not out.exists()
