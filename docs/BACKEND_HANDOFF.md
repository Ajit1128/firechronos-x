# FireChronos X — Entrega técnica del backend (MVP)

**Estado:** prototipo científico funcional; normalización de esquema y análisis de proximidad exploratorio, **no** armonización intersensor validada.

**Responsable principal:** Integrante 1 (Scientific Data & Backend). Revisión de calidad y cumplimiento: Integrante 3. Integración React: Integrante 2.

## Componentes verificados en el código

| Componente | Ubicación | Función |
|---|---|---|
| Normalización NASA FIRMS | `firechronos/pipeline.py` | Valida CSV, conserva columnas originales relevantes, versión, procedencia y huellas SHA-256. No calibra sensores. |
| Procesamiento de dos sensores | `scripts/process_firms.py` | Produce detecciones normalizadas, conteos diarios y un informe de calidad. |
| Comparación espaciotemporal | `scripts/compare_spatiotemporal.py` | Busca candidatos MODIS próximos a detecciones VIIRS en espacio y tiempo. No establece correspondencia uno-a-uno. |
| Auditoría terrestre de Panamá | `scripts/audit_panama_geography.py` | Marca detecciones dentro/fuera de un polígono terrestre ADM0. No descarta automáticamente detecciones. |
| API de solo lectura | `firechronos/api.py` | Expone `/health`, `/summary`, `/daily-counts`, `/detections`. |
| Pruebas | `tests/` | Validación sintética, API, geografía y proximidad. |
| Evidencia resumida | `docs/evidence/panama_march_2024_manifest.json` | Huellas de archivos y resultados declarados para marzo de 2024. |

## Instalación local (Windows PowerShell)

Desde la raíz del repositorio, con Python 3.12 disponible:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

En una verificación local realizada por el integrante 1 el 15 de noviembre de 2026, un **nuevo entorno virtual** instaló las dependencias, `pip check` no encontró conflictos y `pytest` reportó **30 passed, 1 warning** (deprecación de Starlette/TestClient). Esa verificación reutilizó el árbol de trabajo; **no fue una clonación limpia de GitHub ni una reproducción de los CSV de NASA**.

## Procesamiento científico (se requieren CSV originales)

Mantener los CSV originales sin editar. Copiarlos bajo `data/raw/` u otra ruta local excluida de Git, y utilizar rutas reales:

```powershell
.\.venv\Scripts\python.exe .\scripts\process_firms.py `
  --modis "RUTA_AL_CSV_ORIGINAL_MODIS" `
  --viirs "RUTA_AL_CSV_ORIGINAL_VIIRS" `
  --output ".\data\processed" `
  --start 2024-03-01 --end 2024-03-31
```

Produce `detections_normalized.csv`, `daily_detection_counts.csv` y `quality_report.json`. La columna `source_processing=unverified_archive` declara que el tipo de procesamiento del archivo histórico **no está verificado**; no reinterpretarla como NRT o estándar.

```powershell
.\.venv\Scripts\python.exe .\scripts\compare_spatiotemporal.py `
  --input ".\data\processed\detections_normalized.csv" `
  --output-dir ".\data\processed\comparison" `
  --radius-km 1 --minutes 60
```

Sin `--all-types`, el comparador conserva únicamente `type_raw=0`, y en el código actualizado registra exclusiones por clasificaciones ausentes y no cero. **Para disponer de esos nuevos contadores en JSON existentes hay que regenerar cada escenario**; el manifiesto publicado procede de ejecuciones previas.

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_panama_geography.py `
  --input ".\data\processed\detections_normalized.csv" `
  --output-dir ".\data\processed" `
  --boundary-cache ".\data\reference\panama_adm0.geojson"
```

La auditoría usa `geoBoundaries gbOpen PAN ADM0` (referencia de 2022). El archivo de límite debe coincidir con la huella publicada para reproducir exactamente el resultado. Si falta del caché, el script puede descargarlo de su URL fijada y requiere internet.

## Iniciar la API

Si `data/processed` está dentro del checkout:

```powershell
.\.venv\Scripts\python.exe -m uvicorn firechronos.api:app --host 127.0.0.1 --port 8000
```

Si los resultados están fuera del checkout, primero fijar la variable **en esa sesión PowerShell**:

```powershell
$env:FIRECHRONOS_OUTPUT = (Resolve-Path "RUTA_REAL_A_PROCESSED").Path
.\.venv\Scripts\python.exe -m uvicorn firechronos.api:app --host 127.0.0.1 --port 8000
```

Abrir `http://127.0.0.1:8000/docs` para inspeccionar OpenAPI. `GET /health` puede mostrar `data_ready: false` si el informe no está en la carpeta configurada.

## Límites y riesgos aún abiertos

- Cada fila representa una **detección térmica**, no un incendio individual; no inferir causas humanas.
- Las detecciones MODIS y VIIRS no tienen sensibilidad, tamaño de píxel, cobertura ni umbrales equiparables.
- Proximidad espacial/temporal no valida armonización ni correspondencia física entre eventos.
- Una detección fuera del polígono terrestre ADM0 no es automáticamente errónea.
- Ausencia de detecciones en un día no demuestra cobertura satelital completa ni cero incendios.
- Falta revisar de manera independiente fuentes NASA, etiquetas/versiones históricas y cualquier incertidumbre científica.
- La API no configura CORS; el frontend necesita proxy de desarrollo o CORS restringido aprobado, tarea de integración con el Integrante 2.
- La API actual no implementa paginación completa; `/detections` devuelve hasta 1000 filas solicitadas. La selección de esas filas no constituye una muestra representativa.
- El repositorio actual ignora `data/raw/`, pero **no necesariamente `data/processed/`**. Revisar `git status` y **no** agregar datos locales, credenciales ni respaldos accidentalmente.
- PR #1 debe permanecer pendiente hasta aprobación del Integrante 3 y validación de integración.

## Atribución y licencias de las fuentes (verificar en entrega)

- **NASA FIRMS**: el sistema usa archivos que el proyecto identifica como descargas de NASA FIRMS. Reconocer explícitamente el uso del *Fire Information for Resource Management System (FIRMS)* de NASA, parte de ESDIS. Instrucciones oficiales de reconocimiento: https://www.earthdata.nasa.gov/data/tools/firms y https://appliedsciences.nasa.gov/sites/default/files/2025-04/FIRMS_Part2_QA.pdf. La procedencia original debe corroborarse además con los registros de solicitud/descarga del equipo.
- **geoBoundaries**: citar https://www.geoboundaries.org/ y, para publicaciones, Runfola et al. (2020), https://doi.org/10.1371/journal.pone.0231866. La colección **gbOpen** requiere atribución bajo su política general CC BY 4.0; una licencia de fuente subyacente indicada para una frontera concreta no elimina automáticamente las condiciones de atribución del conjunto distribuido. Consultar metadatos de PAN ADM0 antes de redistribuir la geometría.
- El equipo debe acordar por separado la **licencia del código** y declarar el **uso de IA** conforme a las reglas del challenge; estos documentos no certifican tal cumplimiento.

## Checklist de aceptación para el Integrante 3

- [ ] Clon nuevo en directorio independiente; instalación desde `requirements.txt` y `pytest` sin depender del ambiente anterior.
- [ ] Recuperación verificable de los CSV originales; comprobación de hashes SHA-256 contra el manifiesto.
- [ ] Ejecución completa de normalización con recuentos y hash normalizado cotejados.
- [ ] Ejecución de auditoría terrestre con límite geográfico de hash verificado.
- [ ] Regeneración de los cinco reportes de sensibilidad con parámetros fijados.
- [ ] Prueba de integración React–FastAPI, gestión de errores y CORS/proxy.
- [ ] Revisión de licencias, atribuciones NASA/geoBoundaries y descripción del uso de IA.
- [ ] Confirmación de que los cambios científicos y documentación reflejan la misma versión de datos y código.
