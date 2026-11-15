
import { useState } from 'react'
import './App.css'

const modules = [
  { name: 'Dashboard', icon: '◫' },
  { name: 'Fire Atlas', icon: '◎' },
  { name: 'Fire Calendar', icon: '▦' },
  { name: 'Sensor Truth', icon: '⚖' },
]

function App() {
  const [active, setActive] = useState('Dashboard')

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
              className={`nav-item ${active === module.name ? 'selected' : ''}`}
              onClick={() => setActive(module.name)}
              aria-current={active === module.name ? 'page' : undefined}
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
          <div className="eyebrow">SATELLITE FIRE INTELLIGENCE</div>
          <h1>{active}</h1>
          <p className="subtitle">
            Exploring historical thermal detections from
            NASA MODIS and VIIRS satellites.
          </p>

          <div className="notice">
            <span>◉</span>
            Scientific data connection pending.
            No observation results are displayed yet.
          </div>

          <div className="metrics">
            <div className="metric">
              <small>TOTAL DETECTIONS</small>
              <strong>—</strong>
              <span>Awaiting API</span>
            </div>

            <div className="metric">
              <small>MODIS OBSERVATIONS</small>
              <strong>—</strong>
              <span>Awaiting API</span>
            </div>

            <div className="metric">
              <small>VIIRS OBSERVATIONS</small>
              <strong>—</strong>
              <span>Awaiting API</span>
            </div>
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div>
                <h2>{active === 'Dashboard' ? 'Fire Atlas Preview' : active}</h2>
                <p>
                  {active === 'Fire Atlas'
                    ? 'Geospatial visualization of NASA thermal detections'
                    : active === 'Fire Calendar'
                    ? 'Historical observation activity by date'
                    : active === 'Sensor Truth'
                    ? 'Transparent comparison of MODIS and VIIRS'
                    : 'Satellite observation workspace'}
                </p>
              </div>
              <span className="panel-tag">PANAMA</span>
            </div>

            <div className="map-placeholder">
              <div className="orbit">◎</div>
              <h3>Scientific Visualization</h3>
              <p>
                This workspace will display verified NASA data
                when the backend is connected.
              </p>
              <span>DATA SOURCE: NASA FIRMS</span>
            </div>
          </div>

          <footer>
            FIRECHRONOS X · NASA SPACE APPS CHALLENGE 2026
          </footer>
        </section>
      </main>
    </div>
  )
}

export default App
