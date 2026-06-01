"""
Idempotency guard: replaying the same message_id must produce exactly 1 side-effect.
"""
import time
import pytest


def test_idempotency_replay(client):
    """
    Send the same message_id twice.
    Both responses should return the same intent/status.
    Events count must not increase on second call.
    """
    uid = f"idem_test_{int(time.time())}"
    payload = {
        "property_id": "hotel_a",
        "guest_id": "guest_idem",
        "message_id": uid,
        "text": "please give me a wake up call at 7am",
    }

    # First call
    r1 = client.post("/message", json=payload)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["intent"] == "wakeup"
    assert d1["status"] == "processed"

    # Grab event count after first call
    time.sleep(0.5)  # let the queue worker process
    events_r1 = client.get(f"/events?property_id=hotel_a").json()
    count_after_first = sum(
        1 for e in events_r1["events"]
        if e.get("message_id") == uid
    )

    # Second call — replay same message_id
    r2 = client.post("/message", json=payload)
    assert r2.status_code == 200
    d2 = r2.json()
    # Should return stored result, not re-process
    assert d2["intent"] == d1["intent"]
    assert d2["status"] == d1["status"]

    # Event count must not increase
    time.sleep(0.5)
    events_r2 = client.get(f"/events?property_id=hotel_a").json()
    count_after_second = sum(
        1 for e in events_r2["events"]
        if e.get("message_id") == uid
    )

    assert count_after_second == count_after_first, (
        f"Replay produced extra events: before={count_after_first} after={count_after_second}"
    )
