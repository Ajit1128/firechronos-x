# FireChronos X — Contrato para React / FastAPI (fase MVP)

**Estado**: parche de integración propuesto. No supone armonización científica validada. Requiere prueba de navegador por Integrante 2.

## Datos reales de marzo de 2024

El paquete de datos verificado contiene **4,322 observaciones térmicas** (674 MODIS y 3,648 VIIRS S-NPP). Cada fila es una detección, **no un incendio individual**. El límite geográfico ADM0 2022 deja 9 puntos fuera del polígono terrestre; no se eliminan automáticamente. La ausencia de detecciones no demuestra cobertura satelital completa.

## API compatible con versiones anteriores

- `GET /health` → objeto `{"status":"ok","data_ready":true}` cuando existe `quality_report.json`.
- `GET /summary` → objeto del informe de calidad con `record_count_total`.
- `GET /daily-counts?sensor=MODIS` (sensor opcional) → lista de filas con detecciones por fecha y sensor.
- `GET /detections?sensor=MODIS&limit=1000&offset=0` → **lista de detecciones**, en orden original del CSV, *sin cambiar el formato anterior*. `limit`: 1–1000, defecto 100. `offset`: entero >= 0, defecto 0. El desplazamiento se aplica **después** del filtro `sensor`.

Para recuperar las 4,322 filas sin truncamiento, recorrer offsets `0, 1000, 2000, 3000, 4000` con `limit=1000`; la última página devuelve 322. No usar una sola petición con `limit=4322` (422). Continuar páginas hasta que `len(page) < limit`; evitar mezclar con filtros diferentes. Para un conjunto actualizado durante la lectura, paginación por `offset` podría duplicar/saltar filas; el MVP consume una instantánea CSV estática.

Ejemplo TypeScript (llamar desde React, manejar errores y loading states):

```ts
export async function fetchAllDetections(base = '/api'): Promise<unknown[]> {
  const pageSize = 1000;
  const detections: unknown[] = [];
  for (let offset = 0; ; offset += pageSize) {
    const res = await fetch(`${base}/detections?limit=${pageSize}&offset=${offset}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const page: unknown[] = await res.json();
    detections.push(...page);
    if (page.length < pageSize) break;
  }
  return detections;
}
```

## Vite proxy (preferido para desarrollo)

En `vite.config.ts` del **frontend** (responsabilidad Integrante 2), configurar el proxy:

```ts
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, ''),
    },
  },
},
```

Esto permite llamar `/api/detections` desde React sin CORS; no confundir con endpoints `/api` reales del backend. La configuración debe integrarse en el archivo Vite existente, no sustituir su contenido.

## CORS controlado, sin proxy

Se aceptan **solo** `http://localhost:5173` y `http://127.0.0.1:5173` por defecto. Configuración para despliegue:

```powershell
$env:FIRECHRONOS_CORS_ORIGINS='https://tu-frontend.ejemplo'
```

Lista separada por comas si hay más de un origen confiable. Reiniciar Uvicorn después de cambiarla. No usar `*` en producción ni publicar credenciales. Para validar:

```powershell
curl.exe -i -X OPTIONS http://127.0.0.1:8000/detections -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET"
```

Debe devolver `200` y `Access-Control-Allow-Origin: http://localhost:5173`. Un origen no autorizado no debe obtener esa cabecera.

## Reproducción / aceptación

```powershell
python -m pytest -q
$env:FIRECHRONOS_OUTPUT = (Resolve-Path '..\firechronos-x\data\processed').Path
python -m uvicorn firechronos.api:app --host 127.0.0.1 --port 8000
```

Con el servidor encendido, `GET /summary` debe devolver `record_count_total=4322`; cinco peticiones paginadas deben sumar 4,322 (no 4,322 incendios). La auditoría geográfica y proximidad continúan en artefactos separados; **no** se exponen nuevos endpoints en este parche.

### Dependencias / límites

- Backend: Integrante 1 modifica `firechronos/api.py` y `tests/test_api_contract.py`.
- Integrante 2 configura el proxy e integra carga/paginación, mapa y calendario.
- Integrante 3 valida pruebas en navegador, atribuciones y hechos científicos.
- El CSV fuente no forma parte del repositorio público; `FIRECHRONOS_OUTPUT` señala la carpeta local con resultados.
- Cambios científicos y resultados de marzo no implican harmonización MODIS/VIIRS validada.
