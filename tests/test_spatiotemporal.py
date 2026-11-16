"""All examples are SYNTHETIC test coordinates, not observations from NASA."""
import pandas as pd
import pytest

from scripts.compare_spatiotemporal import compare


def row(sensor, latitude, longitude, when, n, kind="0"):
    return {"sensor": sensor, "latitude": latitude, "longitude": longitude,
            "acquired_at_utc": when, "source_file": "SYNTHETIC.csv",
            "source_row": n, "type_raw": kind}


def test_nearby_in_time_and_distance_gives_one_candidate():
    data = pd.DataFrame([
        row("MODIS", 8.5, -80, "2024-03-01T10:00:00Z", 2),
        row("VIIRS_SNPP", 8.5005, -80, "2024-03-01T10:30:00Z", 3),
        row("VIIRS_SNPP", 9.8, -80, "2024-03-01T10:30:00Z", 4),
    ])
    pairs, report = compare(data, radius_km=1.0, minutes=60)
    assert len(pairs) == report["viirs_rows_with_candidate"] == 1
    assert pairs.iloc[0]["viirs_source_row"] == 3
    assert pairs.iloc[0]["distance_km"] < 0.1
    assert pairs.iloc[0]["time_difference_minutes"] == 30


def test_exceeds_time_window_without_match():
    data = pd.DataFrame([
        row("MODIS", 8.5, -80, "2024-03-01T10:00:00Z", 2),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T12:00:00Z", 3),
    ])
    pairs, _ = compare(data)
    assert pairs.empty


def test_cross_midnight_is_allowed_if_within_time_window():
    data = pd.DataFrame([
        row("MODIS", 8.5, -80, "2024-03-02T00:10:00Z", 2),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T23:50:00Z", 3),
    ])
    pairs, _ = compare(data)
    assert len(pairs) == 1
    assert pairs.iloc[0]["time_difference_minutes"] == 20


def test_type_filter_and_invalid_parameters():
    data = pd.DataFrame([
        row("MODIS", 8.5, -80, "2024-03-01T10:00:00Z", 2),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T10:30:00Z", 3, "3"),
    ])
    assert compare(data)[0].empty
    assert len(compare(data, type_zero_only=False)[0]) == 1
    with pytest.raises(ValueError, match="positive"):
        compare(data, radius_km=0)


def test_missing_type_is_reported_not_imputed():
    """Missing classifications are counted, not silently assumed vegetation fires."""
    data = pd.DataFrame([
        row("MODIS", 8.5, -80, "2024-03-01T10:00:00Z", 2, "0"),
        row("MODIS", 8.5, -80, "2024-03-01T10:00:00Z", 3, None),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T10:30:00Z", 4, ""),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T10:30:00Z", 5, "3"),
        row("VIIRS_SNPP", 8.5, -80, "2024-03-01T10:30:00Z", 6, "0"),
    ])

    pairs, report = compare(data)
    assert len(pairs) == 1
    assert report["input_count"] == 5
    assert report["selected_modis"] == 1
    assert report["selected_viirs"] == 1
    assert report["type_missing_in_input"] == 2
    assert report["type_missing_by_sensor"] == {"MODIS": 1, "VIIRS_SNPP": 1}
    assert report["excluded_missing_type"] == 2
    assert report["excluded_other_type"] == 1

    all_pairs, all_report = compare(data, type_zero_only=False)
    assert len(all_pairs) == 3
    assert all_report["type_missing_in_input"] == 2
    assert all_report["excluded_missing_type"] == 0
    assert all_report["excluded_other_type"] == 0
