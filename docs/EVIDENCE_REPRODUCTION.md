# FireChronos X — Evidencia reproducible (Panamá, marzo de 2024)

Los valores de esta tabla se copian del **manifiesto publicado** `docs/evidence/panama_march_2024_manifest.json`; no son mediciones recalculadas por este documento. El manifiesto contiene hashes, nombres de archivos y parámetros. El origen NASA debe acreditarse con las solicitudes/descargas oficiales; el hash no autentica por sí solo al proveedor.

## Conjunto histórico

| Sensor | Filas | Nombre CSV original | SHA-256 |
|---|---:|---|---|
| MODIS | 674 | `fire_archive_M-C61_850535.csv` | `72c7019e160cafc307305ce67bdff26ae61e98d5f9d976365a3f08737a682ba3` |
| VIIRS S-NPP | 3648 | `fire_archive_SV-C2_850536.csv` | `03e6f810cea5d3416bdb769e9082685ab3d605d91fabe83522d521acc0aaac24` |
| **Total** | **4322** | marzo 1–31 de 2024 | — |

IDs del archivo FIRMS declarados: MODIS `850535`, VIIRS `850536`. Procesamiento registrado: `unverified_archive`. Las versiones originales de los archivos se mantienen en los datos normalizados. El archivo `detections_normalized.csv` utilizado en la auditoría original tiene SHA-256 `9d75a0e6c09d00230749a780e8cd250f07c6a54a60f2047cacaa212f90357d5e`.

## Auditoría de polígono terrestre

| Resultado ADM0 terrestre | Detecciones |
|---|---:|
| Dentro | 4313 |
| Fuera | 9 |
| Total | 4322 |

La fuente de geometría es `geoBoundaries gbOpen PAN ADM0` (geometría de referencia de 2022). SHA-256 del GeoJSON fijado: `bcd13a0fb945586315b8501513a89d44ac66bd9f51a2b77bc3167371da2f7f46`. Ver `scripts/audit_panama_geography.py` para URL versionada y metodología `covers`. **Fuera del polígono terrestre no significa incendio falso ni error de geolocalización**.

## Sensibilidad espaciotemporal (candidatos exploratorios)

| Escenario | Radio km | Ventana min | Filas VIIRS con candidato | Filas MODIS seleccionadas por candidatos |
|---|---:|---:|---:|---:|
| strict | 0.5 | 30 | 131 | 81 |
| distance | 0.5 | 60 | 150 | 94 |
| time | 1.0 | 30 | 268 | 134 |
| baseline | 1.0 | 60 | 330 | 172 |
| wide | 2.0 | 120 | 473 | 213 |

El algoritmo selecciona el MODIS más cercano dentro de la ventana por cada VIIRS elegible. No es emparejamiento exclusivo 1:1: el mismo MODIS puede estar asociado a varias filas VIIRS. Se excluyen clases distintas de `type=0` por defecto. Los números de candidatos **no son porcentajes de exactitud, detección ni incendios individuales**.

## Cómo repetir los resultados

1. Recuperar ambos CSV originales del archivo NASA FIRMS con procedencia verificable y comprobar que las huellas coincidan con las de esta página.
2. En una copia limpia del repositorio, instalar las dependencias y ejecutar `pytest`; consultar `docs/BACKEND_HANDOFF.md`.
3. Ejecutar `scripts/process_firms.py` con rutas a los dos CSV, `--start 2024-03-01 --end 2024-03-31` y una carpeta de salida local.
4. Verificar que `quality_report.json` declare `674` y `3648`, y que el SHA-256 de `detections_normalized.csv` coincida con el manifiesto. Si no coincide, documentar versiones de Python, pandas y cambios de serialización antes de interpretar resultados.
5. Ejecutar `scripts/audit_panama_geography.py` con el GeoJSON exacto. Comparar su SHA-256 y las cifras 4313/9.
6. Ejecutar el comparador para cada par de parámetros y contrastar los reportes `proximity_report.json`:

```powershell
$python = '.\.venv\Scripts\python.exe'
$inputCsv = '.\data\processed\detections_normalized.csv'
$scenarios = @(
  @{name='strict'; radius=0.5; minutes=30},
  @{name='distance'; radius=0.5; minutes=60},
  @{name='time'; radius=1; minutes=30},
  @{name='baseline'; radius=1; minutes=60},
  @{name='wide'; radius=2; minutes=120}
)
foreach ($s in $scenarios) {
  & $python .\scripts\compare_spatiotemporal.py `
    --input $inputCsv `
    --output-dir ".\data\processed\comparison_$($s.name)" `
    --radius-km $s.radius --minutes $s.minutes
  if ($LASTEXITCODE -ne 0) { throw "Fallo escenario $($s.name)" }
}
```

**Nota de versión y rutas:** los reportes listados en el manifiesto se generaron **antes** de la incorporación de contadores de `type` ausentes. En los ejemplos actuales, el escenario `baseline` se guarda en `comparison_baseline/`, mientras que la ejecución histórica original utilizó `comparison/`. Es una diferencia de carpeta, no de umbrales. Es necesario regenerar los cinco escenarios desde el código actualizado para incorporar los nuevos campos. No modificar el manifiesto ni declarar equivalencia exacta hasta verificar las nuevas salidas.

## Integridad y procedencia

- Los hashes SHA-256 verifican integridad relativa a los archivos utilizados; no sustituyen una prueba de descarga desde NASA ni validación científica.
- No subir CSV brutos, datos procesados locales, credenciales, rutas personales ni respaldos al PR sin revisión explícita.
- Documentar fecha, URL/procedimiento de adquisición, producto exacto, filtros espaciales/temporales y licencia/atribución oficial antes de la entrega NASA.
- El producto no calibra MODIS frente a VIIRS, no corrige diferencias de cobertura y no cuantifica incertidumbre de detección.

### Reconocimientos y licencias por verificar

- NASA FIRMS: https://www.earthdata.nasa.gov/data/tools/firms. NASA solicita reconocer el uso de datos o imágenes de FIRMS, parte de ESDIS (véase su material de preguntas frecuentes: https://appliedsciences.nasa.gov/sites/default/files/2025-04/FIRMS_Part2_QA.pdf). Confirmar las citas específicas de los productos MODIS y VIIRS utilizados y la evidencia de descarga.
- geoBoundaries: https://www.geoboundaries.org/; política general de gbOpen y atribución: https://www.geoboundaries.org/api.html; referencia académica Runfola et al. (2020): https://doi.org/10.1371/journal.pone.0231866. Consultar la licencia de fuente del registro PAN ADM0, además de las reglas generales del proveedor.

**Pendiente**: completar metadatos de solicitud NASA, licencia del software y declaración de IA antes de la entrega pública del proyecto.
