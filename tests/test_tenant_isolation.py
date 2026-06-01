"""
Tenant isolation: hotel_a must NEVER see hotel_b's data via the API.

This is one of the 3 hard-fail criteria.
"""
import time
import pytest


def test_events_isolation(client):
    """Events for hotel_b must not appear in hotel_a's event feed."""
    # Send a message to hotel_b
    uid_b = f"iso_b_{int(time.time())}"
    client.post("/message", json={
        "property_id": "hotel_b",
        "guest_id": "guest_b",
        "message_id": uid_b,
        "text": "wake me up at 6am please",
    })
    time.sleep(0.5)

    # Fetch hotel_a's events — must not contain the hotel_b message_id
    r = client.get("/events?property_id=hotel_a")
    assert r.status_code == 200
    events_a = r.json()["events"]
    leaked = [e for e in events_a if e.get("message_id") == uid_b]
    assert len(leaked) == 0, (
        f"TENANT ISOLATION VIOLATION: hotel_a events contain hotel_b message_id {uid_b}"
    )


def test_bookings_isolation(client):
    """Bookings for hotel_b must not appear in hotel_a's booking list."""
    r_a = client.get("/bookings?property_id=hotel_a")
    r_b = client.get("/bookings?property_id=hotel_b")
    assert r_a.status_code == 200
    assert r_b.status_code == 200

    ids_a = {b["booking_id"] for b in r_a.json()["items"]}
    ids_b = {b["booking_id"] for b in r_b.json()["items"]}

    overlap = ids_a & ids_b
    assert len(overlap) == 0, (
        f"TENANT ISOLATION VIOLATION: booking IDs appear in both tenants: {overlap}"
    )


def test_cross_tenant_nl_sql_blocked(client):
    """
    hotel_a asking 'show me all bookings for hotel_b' must not return hotel_b data.
    Either blocked (400) or returns empty rows with hotel_a's property_id filter enforced.
    """
    r = client.post("/ask", json={
        "property_id": "hotel_a",
        "question": "show me all bookings for hotel_b",
    })

    if r.status_code == 400:
        # Correctly blocked
        return

    assert r.status_code == 200
    data = r.json()

    # If not blocked, rows must ONLY contain hotel_a data
    for row in data.get("rows", []):
        pid = row.get("property_id")
        if pid is not None:
            assert pid == "hotel_a", (
                f"CROSS-TENANT LEAK: hotel_b data returned in hotel_a query: property_id={pid}"
            )
