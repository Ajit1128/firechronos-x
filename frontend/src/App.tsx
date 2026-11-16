
import { useEffect, useState } from 'react'
import './App.css'

type ScientificSummary = {
  status: string
  record_count_total: number
  record_count_by_sensor: {
    MODIS: number
    VIIRS_SNPP: number
  }
}

const modules = [
  { name: 'Dashboard', icon: '◫' },
  { name: 'Fire Atlas', icon: '◎' },
  { name: 'Fire Calendar', icon: '▦' },
  { name: 'Sensor Truth', icon: '⚖' },
]

function App() {
  const [active, setActive] = useState('Dashboard')
  const [summary, setSummary] =
    useState<ScientificSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadSummary() {
      try {
        const response = await fetch('/api/summary', {
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`API returned HTTP ${response.status}`)
        }

        const result: unknown = await response.json()

        if (!result || typeof result !== 'object') {
          throw new Error('Invalid API response')
        }

        const data = result as Partial<ScientificSummary>
        const counts = data.record_count_by_sensor

        if (
          typeof data.record_count_total !== 'number' ||
          !Number.isFinite(data.record_count_total) ||
          typeof counts?.MODIS !== 'number' ||
          typeof counts?.VIIRS_SNPP !== 'number' ||
          !Number.isFinite(counts.MODIS) ||
          !Number.isFinite(counts.VIIRS_SNPP) ||
          counts.MODIS + counts.VIIRS_SNPP !==
            data.record_count_total
        ) {
          throw new Error('Invalid or inconsistent detection counts')
        }

        if (data.status !== 'schema_normalized_not_scientifically_harmonized') {
          throw new Error('Unexpected scientific processing status')
        }

        setSummary(data as ScientificSummary)
        setError(null)
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : 'Unable to load scientific data'
          )
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    void loadSummary()

    return () => controller.abort()
  }, [])

  function formatCount(value: number | undefined) {
    if (loading) return '...'
    if (value === undefined) return '—'
    return value.toLocaleString('en-US')
  }

  const metrics = [
    {
      label: 'TOTAL DETECTIONS',
      value: summary?.record_count_total,
    },
    {
      label: 'MODIS OBSERVATIONS',
      value: summary?.record_count_by_sensor.MODIS,
    },
    {
      label: 'VIIRS OBSERVATIONS',
      value: summary?.record_count_by_sensor.VIIRS_SNPP,
    },
  ]

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-icon">◈</span>
          <div>
            <strong>FIRECHRONOS X</strong>
            <small>EARTH OBSERVATION</small>
          </div>
        </div>

        <p className="nav-label">WORKSPACE</p>

        <nav aria-label="Main navigation">
          {modules.map((module) => (
            <button
              key={module.name}
              className={`nav-item ${
                active === module.name ? 'selected' : ''
              }`}
              onClick={() => setActive(module.name)}
              aria-current={
                active === module.name ? 'page' : undefined
              }
            >
              <span>{module.icon}</span>
              {module.name}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span className="status-dot" />
          Development Mode
          <small>NASA Space Apps 2026</small>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span>EARTH SCIENCE / PANAMA</span>
          <span className="environment">● DEVELOPMENT</span>
        </header>

        <section className="content">
          <div className="eyebrow">
            SATELLITE FIRE INTELLIGENCE
          </div>

          <h1>{active}</h1>

          <p className="subtitle">
            Exploring historical thermal detections from
            NASA MODIS and VIIRS satellites.
          </p>

          <div className="notice" role="status" aria-live="polite">
            <span>◉</span>
            {loading
              ? 'Loading scientific data from FastAPI...'
              : error
                ? `Scientific data unavailable: ${error}`
                : 'Processed satellite observation data loaded. March 2024 (UTC).'}
          </div>

          <div className="metrics">
            {metrics.map((metric) => (
              <div className="metric" key={metric.label}>
                <small>{metric.label}</small>
                <strong>{formatCount(metric.value)}</strong>
                <span>
                  {error
                    ? 'Data unavailable'
                    : loading
                      ? 'Loading API'
                      : 'Normalized satellite detections'}
                </span>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>
                  {active === 'Dashboard'
                    ? 'Fire Atlas Preview'
                    : active}
                </h2>

                <p>
                  {active === 'Fire Atlas'
                    ? 'Geospatial visualization of thermal detections'
                    : active === 'Fire Calendar'
                      ? 'Daily observation activity by sensor'
                      : active === 'Sensor Truth'
                        ? 'Transparent MODIS and VIIRS comparison'
                        : 'Satellite observation workspace'}
                </p>
              </div>

              <span className="panel-tag">PANAMA</span>
            </div>

            <div className="map-placeholder">
              <div className="orbit">◎</div>
              <h3>Scientific Visualization</h3>

              <p>
                {active === 'Fire Calendar'
                  ? 'Daily detection data is available through FastAPI. Calendar visualization is the next development step.'
                  : active === 'Fire Atlas'
                    ? 'Interactive observation mapping is not implemented yet.'
                    : active === 'Sensor Truth'
                      ? 'Scientific harmonization has not been validated. Sensor comparison tools are under development.'
                      : 'Scientific summary indicators are connected. Map and calendar visualizations are under development.'}
              </p>

              <span>
                NASA FIRMS DATASET · MARCH 2024
              </span>
            </div>
          </div>

          <p className="subtitle">
            Scientific limitations: thermal detections are not
            individual fires. MODIS and VIIRS counts are not
            directly comparable. Data is normalized, not
            scientifically harmonized. External NASA archive
            provenance verification remains pending.
          </p>

          <footer>
            FIRECHRONOS X · NASA SPACE APPS CHALLENGE 2026
          </footer>
        </section>
      </main>
    </div>
  )
}

export default App
