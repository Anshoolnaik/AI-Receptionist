import { useState } from 'react'
import { api, Event, Booking } from '../api/client'
import { usePolling } from '../hooks/usePolling'

interface Props { propertyId: string }

type Tab = 'events' | 'bookings'

export default function LifecycleFeed({ propertyId }: Props) {
  const [tab, setTab] = useState<Tab>('events')

  const events = usePolling(
    () => api.getEvents(propertyId).then(r => r.events),
    5000,
    [propertyId]
  )
  const bookings = usePolling(
    () => api.getBookings(propertyId).then(r => r.items),
    5000,
    [propertyId]
  )

  const active = tab === 'events' ? events : bookings

  return (
    <div>
      <div className="tabs">
        <button
          className={`tab-btn ${tab === 'events' ? 'active' : ''}`}
          onClick={() => setTab('events')}
        >Events</button>
        <button
          className={`tab-btn ${tab === 'bookings' ? 'active' : ''}`}
          onClick={() => setTab('bookings')}
        >Bookings</button>
      </div>

      {active.loading && <p className="loading">Loading…</p>}
      {active.error && <p className="error">Error: {active.error}</p>}

      {!active.loading && !active.error && (
        tab === 'events'
          ? <EventList items={events.data ?? []} />
          : <BookingList items={bookings.data ?? []} />
      )}
    </div>
  )
}

function EventList({ items }: { items: Event[] }) {
  if (items.length === 0) return <p className="empty">No events yet.</p>
  return (
    <ul className="feed-list">
      {items.map(e => (
        <li key={e.event_id} className="feed-item">
          <div className="feed-item-type">{e.event_type.replace(/_/g, ' ')}</div>
          <div className="feed-item-meta">
            {new Date(e.created_at).toLocaleString()}
            {e.message_id && ` · msg: ${e.message_id}`}
          </div>
          {e.payload && (
            <div className="feed-item-payload">
              {JSON.stringify(e.payload)}
            </div>
          )}
        </li>
      ))}
    </ul>
  )
}

const STATUS_COLORS: Record<string, string> = {
  confirmed: '#276749',
  cancelled: '#c53030',
  no_show: '#744210',
  checked_out: '#2b6cb0',
}

function BookingList({ items }: { items: Booking[] }) {
  if (items.length === 0) return <p className="empty">No bookings yet.</p>
  return (
    <ul className="feed-list">
      {items.map(b => (
        <li key={b.booking_id} className="feed-item">
          <div className="feed-item-type" style={{ color: STATUS_COLORS[b.status] ?? '#553c9a' }}>
            {b.status.replace(/_/g, ' ')} · {b.room_type}
          </div>
          <div className="feed-item-meta">
            {b.checkin ?? '?'} → {b.checkout ?? '?'} · ₹{b.amount_inr} · {b.source}
          </div>
        </li>
      ))}
    </ul>
  )
}
