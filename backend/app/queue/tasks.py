"""Task dataclasses enqueued by workflow handlers and consumed by the worker."""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EventLogTask:
    """Write an event row to the events table."""
    type: str = "event_log"
    property_id: str = ""
    message_id: str | None = None
    event_type: str = ""
    payload: dict = field(default_factory=dict)


@dataclass
class BookingCreateTask:
    """Create a booking row then optionally push to OTA."""
    type: str = "booking_create"
    property_id: str = ""
    message_id: str = ""
    booking_data: dict = field(default_factory=dict)
    push_to_ota: bool = True


@dataclass
class OTAPushTask:
    """Push availability update to the mock OTA (retried on 429/500)."""
    type: str = "ota_push"
    property_id: str = ""
    push_id: str = ""        # idempotency key — use booking_id
    payload: dict = field(default_factory=dict)
