
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


def test_pagination_with_sensor_and_invalid_offset(client):
    first = client.get("/detections", params={"limit": 2, "offset": 0})
    next_page = client.get("/detections", params={"limit": 2, "offset": 2})
    assert first.status_code == next_page.status_code == 200
    assert len(first.json()) == 2
    assert len(next_page.json()) == 1
    assert first.json() + next_page.json() == client.get(
        "/detections", params={"limit": 10}
    ).json()
    assert client.get("/detections?limit=2&offset=-1").status_code == 422
    assert client.get("/detections?limit=2&offset=999").json() == []
    viirs = client.get("/detections", params={
        "sensor": "VIIRS_SNPP", "limit": 1, "offset": 1,
    })
    assert viirs.status_code == 200
    assert viirs.json()[0]["type_raw"] == 3


def test_4322_rows_retrievable_in_five_pages(client, tmp_path):
    path = tmp_path / "detections_normalized.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("sensor,source_row\n")
        for i in range(4322):
            handle.write(f"{('MODIS' if i < 674 else 'VIIRS_SNPP')},{i}\n")
    rows = []
    for offset in range(0, 4322, 1000):
        response = client.get("/detections", params={
            "limit": 1000, "offset": offset,
        })
        assert response.status_code == 200
        rows.extend(response.json())
    assert len(rows) == 4322
    assert [r["source_row"] for r in rows] == list(range(4322))
    assert client.get("/detections?limit=1000&offset=4322").json() == []


def test_offset_across_csv_chunks_and_filtered_rows(client, tmp_path):
    path = tmp_path / "detections_normalized.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("sensor,source_row\n")
        for i in range(5100):
            handle.write(f"{('MODIS' if i % 2 else 'VIIRS_SNPP')},{i}\n")
    response = client.get("/detections", params={
        "sensor": "VIIRS_SNPP", "offset": 2498, "limit": 5,
    })
    assert response.status_code == 200
    assert [row["source_row"] for row in response.json()] == [4996, 4998, 5000, 5002, 5004]


def test_cors_dev_origin_preflight(client):
    response = client.options("/detections", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_untrusted_origin_rejected(client):
    response = client.options("/detections", headers={
        "Origin": "https://untrusted.example",
        "Access-Control-Request-Method": "GET",
    })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
