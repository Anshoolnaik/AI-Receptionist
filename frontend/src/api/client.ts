const BASE = import.meta.env.VITE_BACKEND_URL ?? 'http://localhost:8000'

export interface Event {
  event_id: string
  property_id: string
  message_id: string | null
  event_type: string
  payload: Record<string, unknown> | null
  created_at: string
}

export interface Booking {
  booking_id: string
  property_id: string
  room_type: string
  checkin: string | null
  checkout: string | null
  status: string
  amount_inr: number
  source: string
}

export interface AskResponse {
  answer: string | null
  sql: string | null
  rows: Record<string, unknown>[]
  source: string | null
  refused: boolean
  note: string | null
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`${res.status}: ${detail}`)
  }
  return res.json()
}

export const api = {
  getEvents: (propertyId: string) =>
    get<{ events: Event[] }>(`/events?property_id=${propertyId}`),
  getBookings: (propertyId: string) =>
    get<{ items: Booking[] }>(`/bookings?property_id=${propertyId}`),
  ask: (propertyId: string, question: string) =>
    post<AskResponse>('/ask', { property_id: propertyId, question }),
}
