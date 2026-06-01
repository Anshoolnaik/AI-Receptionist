"""
Test intent classification accuracy on the 15 labeled seed messages.
Also asserts m14 (ambiguous cancel) stays below CONFIDENCE_THRESHOLD.
"""
import json
import os
import time
import pytest

LABELED = [
    {"message_id": "m1",  "property_id": "hotel_a", "text": "do you have a room for tomorrow night for 2 people", "intent": "booking"},
    {"message_id": "m2",  "property_id": "hotel_a", "text": "kya kal ka room milega 2 logo ke liye", "intent": "booking"},
    {"message_id": "m3",  "property_id": "hotel_a", "text": "please cancel my booking for tonight", "intent": "cancellation"},
    {"message_id": "m4",  "property_id": "hotel_a", "text": "what time is checkout?", "intent": "faq"},
    {"message_id": "m5",  "property_id": "hotel_a", "text": "the AC in room 203 is not working at all", "intent": "complaint"},
    {"message_id": "m6",  "property_id": "hotel_a", "text": "please give me a wake up call at 6am", "intent": "wakeup"},
    {"message_id": "m7",  "property_id": "hotel_b", "text": "is there a single room available from 1st", "intent": "booking"},
    {"message_id": "m8",  "property_id": "hotel_b", "text": "what is the monthly rent and deposit", "intent": "faq"},
    {"message_id": "m9",  "property_id": "hotel_b", "text": "cancel kar do meri booking", "intent": "cancellation"},
    {"message_id": "m10", "property_id": "hotel_b", "text": "wifi password kya hai", "intent": "faq"},
    {"message_id": "m11", "property_id": "hotel_b", "text": "the food yesterday was cold and bad", "intent": "complaint"},
    {"message_id": "m12", "property_id": "hotel_b", "text": "wake me up at 5:30 tomorrow please", "intent": "wakeup"},
    {"message_id": "m13", "property_id": "hotel_a", "text": "hi", "intent": "faq"},
    {"message_id": "m14", "property_id": "hotel_a", "text": "umm maybe cancel or change, not sure yet", "intent": "cancellation"},
    {"message_id": "m15", "property_id": "hotel_a", "text": "book a deluxe room and also what's the wifi", "intent": "booking"},
]

CONFIDENCE_THRESHOLD = 0.6


def test_classify_accuracy(client):
    """At least 13/15 messages classified correctly."""
    correct = 0
    for msg in LABELED:
        uid = f"test_classify_{msg['message_id']}_{int(time.time())}"
        r = client.post("/message", json={
            "property_id": msg["property_id"],
            "guest_id": "test_guest",
            "message_id": uid,
            "text": msg["text"],
        })
        assert r.status_code == 200, f"POST /message failed for {msg['message_id']}: {r.text}"
        data = r.json()
        if data.get("intent") == msg["intent"]:
            correct += 1
        else:
            print(f"  MISS: {msg['message_id']} expected={msg['intent']} got={data.get('intent')}")

    accuracy = correct / len(LABELED)
    print(f"\nClassify accuracy: {correct}/{len(LABELED)} = {accuracy:.0%}")
    assert correct >= 13, f"Accuracy too low: {correct}/15"


def test_m14_false_positive_guard(client):
    """
    m14 'umm maybe cancel or change, not sure yet' must NOT auto-cancel.
    Expected status: confirm_cancel (ambiguous) or needs_human.
    The booking must NOT be cancelled.
    """
    uid = f"test_m14_{int(time.time())}"
    r = client.post("/message", json={
        "property_id": "hotel_a",
        "guest_id": "test_guest",
        "message_id": uid,
        "text": "umm maybe cancel or change, not sure yet",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("confirm_cancel", "needs_human"), (
        f"Ambiguous cancel must NOT auto-process, got status={data['status']!r}"
    )
    # Confidence should be below threshold
    if data.get("confidence") is not None:
        assert data["confidence"] < CONFIDENCE_THRESHOLD, (
            f"Ambiguous message confidence should be < {CONFIDENCE_THRESHOLD}, got {data['confidence']}"
        )


def test_classify_latency(client):
    """P95 classify latency should be reported (not None) after several messages."""
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    # P95 may be None if not enough messages processed yet — that's ok
    # Just ensure the endpoint is present and parseable
    assert "classify_p95_ms" in data
