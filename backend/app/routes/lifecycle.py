"""GET /events and GET /bookings — both tenant-scoped via RLS."""
from fastapi import APIRouter
from app.database import rls_cursor

router = APIRouter()


@router.get("/events")
def get_events(property_id: str, limit: int = 50):
    with rls_cursor(property_id) as cur:
        cur.execute(
            """
            SELECT event_id, property_id, message_id, event_type, payload, created_at
            FROM events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return {
        "property_id": property_id,
        "events": [dict(r) for r in rows],
    }


@router.get("/bookings")
def get_bookings(property_id: str, limit: int = 50):
    with rls_cursor(property_id) as cur:
        cur.execute(
            """
            SELECT booking_id, property_id, room_type, checkin, checkout,
                   status, amount_inr, source
            FROM bookings
            ORDER BY checkin DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return {
        "property_id": property_id,
        "items": [dict(r) for r in rows],
    }
