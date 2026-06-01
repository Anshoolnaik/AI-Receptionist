import { useState } from 'react'
import LifecycleFeed from './components/LifecycleFeed'
import AskAssistant from './components/AskAssistant'
import './app.css'

const PROPERTIES = [
  { id: 'hotel_a', label: 'Hotel Surya (Varanasi)' },
  { id: 'hotel_b', label: 'Coastal Stay PG (Bengaluru)' },
]

export default function App() {
  const [propertyId, setPropertyId] = useState('hotel_a')

  return (
    <div className="app">
      <header className="app-header">
        <h1>🏨 Owner Console</h1>
        <select
          className="property-select"
          value={propertyId}
          onChange={e => setPropertyId(e.target.value)}
          aria-label="Select property"
        >
          {PROPERTIES.map(p => (
            <option key={p.id} value={p.id}>{p.label}</option>
          ))}
        </select>
      </header>

      <main className="app-main">
        <section className="panel">
          <h2>📋 Lifecycle Feed</h2>
          <LifecycleFeed propertyId={propertyId} />
        </section>

        <section className="panel">
          <h2>🤖 Ask the Assistant</h2>
          <AskAssistant propertyId={propertyId} />
        </section>
      </main>
    </div>
  )
}
