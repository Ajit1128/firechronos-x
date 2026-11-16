"""Minimal read-only frontend bridge. Serve only after generating actual outputs."""
from pathlib import Path
import json
import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FireChronos X data prototype", version="0.1.0")
# Explicit development origins only; replace with deployment origins in production.
origins = [
    origin.strip().rstrip("/")
    for origin in os.environ.get(
        "FIRECHRONOS_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)
OUTPUT = Path(os.environ.get("FIRECHRONOS_OUTPUT", "data/processed"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "data_ready": (OUTPUT / "quality_report.json").exists()}


@app.get("/summary")
def summary() -> dict:
    path = OUTPUT / "quality_report.json"
    if not path.is_file():
        raise HTTPException(503, detail="No hay resultados NASA procesados todavía.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/daily-counts")
def daily_counts(sensor: str | None = None) -> list[dict]:
    path = OUTPUT / "daily_detection_counts.csv"
    if not path.is_file():
        raise HTTPException(503, detail="No hay datos NASA procesados todavía.")
    if sensor and sensor not in {"MODIS", "VIIRS_SNPP"}:
        raise HTTPException(400, detail="Sensor inválido")
    df = pd.read_csv(path)
    if sensor:
        df = df[df["sensor"] == sensor]
    return df.to_dict(orient="records")


@app.get("/detections")
def detections(
    sensor: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    path = OUTPUT / "detections_normalized.csv"
    if not path.is_file():
        raise HTTPException(503, detail="No hay datos NASA procesados todavía.")
    if sensor and sensor not in {"MODIS", "VIIRS_SNPP"}:
        raise HTTPException(400, detail="Sensor inválido")
    # Offset applies AFTER filtering; preserve CSV order for repeatable pages.
    # Chunking prevents loading the complete archive into memory.
    results: list[dict] = []
    remaining_skip = offset
    for chunk in pd.read_csv(path, chunksize=5000):
        if sensor:
            chunk = chunk.loc[chunk["sensor"] == sensor]
        if remaining_skip >= len(chunk):
            remaining_skip -= len(chunk)
            continue
        subset = chunk.iloc[remaining_skip:remaining_skip + limit - len(results)]
        remaining_skip = 0
        subset = subset.astype(object)
        subset = subset.where(pd.notna(subset), None)
        results.extend(subset.to_dict(orient="records"))
        if len(results) >= limit:
            break
    return results
