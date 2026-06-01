"""
Full e2e round-trip tests.
Exercises the complete lifecycle: property → message → events → ask.
"""
import time
import pytest


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_full_lifecycle_booking(client):
    """
    End-to-end: send a booking message → wait for queue → event appears in feed.
    """
    uid = f"e2e_booking_{int(time.time())}"
    r = client.post("/message", json={
        "property_id": "hotel_a",
        "guest_id": "e2e_guest",
        "message_id": uid,
        "text": "I need a room for tomorrow night please",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["intent"] == "booking"
    assert d["status"] == "processed"

    # Give queue worker time to fire
    time.sleep(1.0)

    # Check event was logged
    events = client.get("/events?property_id=hotel_a").json()["events"]
    relevant = [e for e in events if e.get("message_id") == uid]
    assert len(relevant) >= 1, "No event found for booking message"


def test_full_lifecycle_faq(client):
    """FAQ message → processed, no booking created."""
    uid = f"e2e_faq_{int(time.time())}"
    r = client.post("/message", json={
        "property_id": "hotel_a",
        "guest_id": "e2e_guest",
        "message_id": uid,
        "text": "what time is checkout?",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["intent"] == "faq"
    assert d["reply"] is not None


def test_full_lifecycle_wakeup(client):
    uid = f"e2e_wakeup_{int(time.time())}"
    r = client.post("/message", json={
        "property_id": "hotel_b",
        "guest_id": "e2e_guest",
        "message_id": uid,
        "text": "wake me up at 5:30am please",
    })
    assert r.status_code == 200
    assert r.json()["intent"] == "wakeup"


def test_full_lifecycle_complaint(client):
    uid = f"e2e_complaint_{int(time.time())}"
    r = client.post("/message", json={
        "property_id": "hotel_b",
        "guest_id": "e2e_guest",
        "message_id": uid,
        "text": "the food yesterday was cold and bad",
    })
    assert r.status_code == 200
    assert r.json()["intent"] == "complaint"
    time.sleep(0.5)
    events = client.get("/events?property_id=hotel_b").json()["events"]
    logged = [e for e in events if e.get("event_type") == "complaint_logged" and e.get("message_id") == uid]
    assert len(logged) >= 1, "Complaint event not logged"


def test_ask_data_question(client):
    """NL→SQL returns answer, sql, and rows."""
    r = client.post("/ask", json={
        "property_id": "hotel_a",
        "question": "how many bookings do we have that are confirmed?",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] is not None
    assert data["sql"] is not None
    assert isinstance(data["rows"], list)


def test_ask_rag_question(client):
    """RAG question returns answer with source."""
    r = client.post("/ask", json={
        "property_id": "hotel_a",
        "question": "how do I change my room rate?",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] is not None
    assert data["source"] is not None


def test_events_endpoint_tenant_scoped(client):
    r = client.get("/events?property_id=hotel_a")
    assert r.status_code == 200
    body = r.json()
    assert body["property_id"] == "hotel_a"
    for e in body["events"]:
        assert e["property_id"] == "hotel_a", "Event from another tenant leaked!"


def test_bookings_endpoint_tenant_scoped(client):
    r = client.get("/bookings?property_id=hotel_b")
    assert r.status_code == 200
    body = r.json()
    assert body["property_id"] == "hotel_b"
    for b in body["items"]:
        assert b["property_id"] == "hotel_b", "Booking from another tenant leaked!"
