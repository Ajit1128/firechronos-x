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


def test_rejects_wrong_modis_collection_without_false_provenance(tmp_path):
    df = pd.read_csv(M, dtype=str)
    df.loc[0, "version"] = "5.0"
    path = tmp_path / "modis_wrong_collection.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Versión/colección incompatible"):
        load_firms_csv(path, "MODIS")


def test_rejects_wrong_viirs_collection(tmp_path):
    df = pd.read_csv(V, dtype=str)
    df.loc[0, "version"] = "1.0"
    path = tmp_path / "viirs_wrong_collection.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Versión/colección incompatible"):
        load_firms_csv(path, "VIIRS_SNPP")


def test_rejects_csv_without_version(tmp_path):
    df = pd.read_csv(M, dtype=str).drop(columns=["version"])
    path = tmp_path / "no_version.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Faltan columnas obligatorias"):
        load_firms_csv(path, "MODIS")


def test_preserves_nrt_processing_separately_from_standard(tmp_path):
    df = pd.read_csv(V, dtype=str)
    df.loc[0, "version"] = "2.0NRT"
    path = tmp_path / "mixed_processing.csv"
    df.to_csv(path, index=False)
    output, metadata = load_firms_csv(path, "VIIRS_SNPP")
    assert output.loc[0, "version"] == "2.0NRT"
    assert output.loc[0, "source_product"] == "suomi-viirs-c2-nrt"
    assert output.loc[0, "source_processing"] == "near_real_time"
    assert output.loc[1, "source_product"] == "suomi-viirs-c2"
    assert output.loc[1, "source_processing"] == "standard"
    assert metadata["source_processing"] == ["near_real_time", "standard"]


def test_rejects_non_snpp_satellite_even_with_viirs_instrument(tmp_path):
    df = pd.read_csv(V, dtype=str)
    df.loc[0, "satellite"] = "N20"
    path = tmp_path / "wrong_satellite.csv"
    df.to_csv(path, index=False)
    with pytest.raises(FIRMSValidationError, match="Satélite incompatible"):
        load_firms_csv(path, "VIIRS_SNPP")

@pytest.mark.parametrize("satellite", ["Terra", "Aqua"])
def test_accepts_modis_archive_satellite_names(tmp_path, satellite):
    df = pd.read_csv(M, dtype=str)
    df.loc[0, "satellite"] = satellite

    path = tmp_path / "modis_archive.csv"
    df.to_csv(path, index=False)

    normalized, _ = load_firms_csv(path, "MODIS")

    assert normalized.loc[0, "satellite"] == satellite


def test_modis_archive_version_61_03(tmp_path):
    df = pd.read_csv(M, dtype=str)
    df["version"] = "61.03"

    path = tmp_path / "modis_archive.csv"
    df.to_csv(path, index=False)

    normalized, _ = load_firms_csv(path, "MODIS")

    assert set(normalized["version"]) == {"61.03"}
    assert set(normalized["source_product"]) == {"modis-c6.1"}
    assert set(normalized["source_processing"]) == {
        "unverified_archive"
    }


def test_accepts_viirs_snpp_archive_identifiers(tmp_path):
    df = pd.read_csv(V, dtype=str)
    df["instrument"] = "SNPP"
    df["satellite"] = "SNPP"
    df["version"] = "2"

    path = tmp_path / "fire_archive_SV-C2_test.csv"
    df.to_csv(path, index=False)

    normalized, _ = load_firms_csv(path, "VIIRS_SNPP")

    assert len(normalized) == len(df)
    assert set(normalized["instrument"]) == {"SNPP"}
    assert set(normalized["satellite"]) == {"SNPP"}
    assert set(normalized["version"]) == {"2"}
    assert set(normalized["source_product"]) == {
        "suomi-viirs-c2"
    }
    assert set(normalized["source_processing"]) == {
        "unverified_archive"
    }


def test_preserves_viirs_confidence_and_type(tmp_path):
    df = pd.read_csv(V, dtype=str)

    df["confidence"] = ["n", "h"]
    df["type"] = ["0", "3"]

    path = tmp_path / "viirs_types.csv"
    df.to_csv(path, index=False)

    normalized, _ = load_firms_csv(
        path, "VIIRS_SNPP"
    )

    assert normalized["confidence_raw"].tolist() == [
        "n", "h"
    ]
    assert normalized["type_raw"].tolist() == [
        "0", "3"
    ]


def test_accepts_modis_without_instrument(tmp_path):
    df = pd.read_csv(M, dtype=str).drop(columns=["instrument"])
    path = tmp_path / "modis_without_instrument.csv"
    df.to_csv(path, index=False)

    normalized, metadata = load_firms_csv(path, "MODIS")

    assert len(normalized) == len(df)
    assert normalized["instrument"].eq("").all()
    assert metadata["instrument_column_present"] is False
    assert "instrument" not in metadata["original_columns"]


def test_rejects_viirs_without_instrument(tmp_path):
    df = pd.read_csv(V, dtype=str).drop(columns=["instrument"])
    path = tmp_path / "viirs_without_instrument.csv"
    df.to_csv(path, index=False)

    with pytest.raises(
        FIRMSValidationError,
        match="Falta columna instrument",
    ):
        load_firms_csv(path, "VIIRS_SNPP")


