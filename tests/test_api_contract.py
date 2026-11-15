
"""Pruebas del contrato API con datos sinteticos."""

import pytest
from fastapi.testclient import TestClient
import firechronos.api as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "quality_report.json").write_text(
        '{"record_count_total": 3}',
        encoding="utf-8",
    )

    (tmp_path / "daily_detection_counts.csv").write_text(
        "acq_date,sensor,detection_count\n"
        "2024-03-01,MODIS,1\n"
        "2024-03-01,VIIRS_SNPP,2\n",
        encoding="utf-8",
    )

    (tmp_path / "detections_normalized.csv").write_text(
        "sensor,latitude,longitude,type_raw\n"
        "MODIS,8.5,-80.0,0\n"
        "VIIRS_SNPP,8.6,-80.1,0\n"
        "VIIRS_SNPP,8.7,-80.2,3\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(api, "OUTPUT", tmp_path)
    return TestClient(api.app)


def test_sensor_filters(client):
    for sensor, expected in [
        ("MODIS", 1),
        ("VIIRS_SNPP", 2),
    ]:
        response = client.get(
            "/detections",
            params={"sensor": sensor, "limit": 10},
        )
        assert response.status_code == 200
        assert len(response.json()) == expected
        assert all(
            row["sensor"] == sensor
            for row in response.json()
        )

        daily = client.get(
            "/daily-counts",
            params={"sensor": sensor},
        )
        assert daily.status_code == 200
        assert len(daily.json()) == 1


def test_invalid_requests(client):
    assert client.get(
        "/detections?limit=1001"
    ).status_code == 422

    assert client.get(
        "/detections?sensor=INVALID"
    ).status_code == 400

    assert client.get(
        "/daily-counts?sensor=INVALID"
    ).status_code == 400
