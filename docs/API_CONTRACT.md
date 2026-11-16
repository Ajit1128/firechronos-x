> **Actualización T89:** Los apartados de paginación y CORS de este documento reflejan el contrato previo. El contrato vigente propuesto se detalla en [API_INTEGRATION_REACT.md](API_INTEGRATION_REACT.md). La integración en navegador aún requiere validación.

# FireChronos X — Contrato API (backend actual)

Fuente de referencia: `firechronos/api.py` de la rama `feature/nasa-firms-backend`. API **solo lectura**, FastAPI `0.1.0`. No se supone disponibilidad pública ni despliegue remoto.

Base local: `http://127.0.0.1:8000` (si Uvicorn está iniciado).

| Método y ruta | Parámetros | Respuesta satisfactoria | Errores relevantes |
|---|---|---|---|
| `GET /health` | ninguno | `{"status":"ok","data_ready":true/false}` | `data_ready=false` no equivale a error HTTP. |
| `GET /summary` | ninguno | objeto JSON de `quality_report.json` | `503` si falta el informe. |
| `GET /daily-counts` | `sensor` opcional: `MODIS` o `VIIRS_SNPP` | lista JSON de conteos por día/sensor | `400` sensor inválido; `503` falta CSV. |
| `GET /detections` | `sensor` opcional; `limit` entero 1..1000 (por defecto 100) | lista JSON de detecciones normalizadas | `400` sensor inválido; `422` límite inválido; `503` falta CSV. |

### Ejemplos

```text
GET /health
GET /summary
GET /daily-counts?sensor=MODIS
GET /daily-counts?sensor=VIIRS_SNPP
GET /detections?sensor=VIIRS_SNPP&limit=100
```

Los conteos diarios se basan en días **con detecciones**, no en una grilla completa de días observados. Los registros de `/detections` contienen, entre otros, `sensor`, `latitude`, `longitude`, `acq_date`, `acquired_at_utc`, `source_file`, `source_row`, `source_product`, `source_processing`, `type_raw`, `confidence_raw`, `frp_mw`. El esquema normalizado se define en `firechronos/pipeline.py`.

Las respuestas `GET /detections` no ofrecen paginación, orden/filtrado temporal explícito ni selección geográfica del lado del servidor. No se debe cargar un catálogo histórico completo con una sola llamada ni presentar las primeras 100 filas como un muestreo representativo.

### Contrato de integración con React (a coordinar con Integrante 2)

La API actual **no declara CORS**. En desarrollo, una opción es configurar en el frontend un proxy Vite para que las llamadas del navegador a `/api/...` se reescriban a `http://127.0.0.1:8000/...`. Esto es una **propuesta de integración**, no una funcionalidad actualmente implementada ni probada. El frontend no debe asumir que existe una ruta `/api` en FastAPI: el prefijo se elimina mediante el proxy de Vite.

El frontend debe manejar `503` (datos aún no preparados), `400`, `422`, conectividad interrumpida y listas vacías. Las etiquetas del dashboard deben decir «detecciones térmicas»; no «número de incendios».

### Prueba rápida

```powershell
# Con el servidor encendido:
Invoke-RestMethod http://127.0.0.1:8000/health
(Invoke-RestMethod http://127.0.0.1:8000/detections?limit=3).Count
```

La prueba automatizada local del integrante 1 verificó los filtros y respuestas sobre el conjunto procesado y se añadieron pruebas sintéticas del contrato a `tests/test_api_contract.py`. La integración de navegador sigue pendiente.
