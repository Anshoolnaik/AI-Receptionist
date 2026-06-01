"""
Async queue worker.

The queue is an asyncio.Queue stored on app.state.queue.
Workflows enqueue tasks (not inline side-effects); this worker processes them.
This proves async decoupling: POST /message returns before DB writes happen.
"""
import asyncio
import uuid
import logging

from app.queue.tasks import EventLogTask, BookingCreateTask, OTAPushTask
from app.database import rls_cursor

logger = logging.getLogger(__name__)


async def queue_worker(queue: asyncio.Queue) -> None:
    """Consume tasks from the queue forever. Runs as a background asyncio task."""
    logger.info("Queue worker started")
    while True:
        task = await queue.get()
        try:
            await _dispatch(task)
        except Exception as exc:
            logger.exception("Queue worker error on task %s: %s", type(task).__name__, exc)
        finally:
            queue.task_done()


async def _dispatch(task) -> None:
    if isinstance(task, EventLogTask):
        await _handle_event_log(task)
    elif isinstance(task, BookingCreateTask):
        await _handle_booking_create(task)
    elif isinstance(task, OTAPushTask):
        await _handle_ota_push(task)
    else:
        logger.warning("Unknown task type: %s", type(task))


async def _handle_event_log(task: EventLogTask) -> None:
    import json
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_event_log, task)


def _sync_event_log(task: EventLogTask) -> None:
    import json
    event_id = str(uuid.uuid4())
    with rls_cursor(task.property_id) as cur:
        cur.execute(
            """
            INSERT INTO events (event_id, property_id, message_id, event_type, payload)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (event_id, task.property_id, task.message_id,
             task.event_type, json.dumps(task.payload))
        )
    logger.info("Event logged: %s %s", task.event_type, event_id)


async def _handle_booking_create(task: BookingCreateTask) -> None:
    loop = asyncio.get_event_loop()
    booking_id = await loop.run_in_executor(None, _sync_create_booking, task)
    if task.push_to_ota and booking_id:
        from app.queue.tasks import OTAPushTask
        ota_task = OTAPushTask(
            property_id=task.property_id,
            push_id=f"{booking_id}_ota",
            payload={
                "property_id": task.property_id,
                "booking_id": booking_id,
                **task.booking_data,
            },
        )
        # Fire-and-forget: OTA push must not block the queue worker.
        # booking_created event is already committed above.
        asyncio.ensure_future(_handle_ota_push(ota_task))


def _sync_create_booking(task: BookingCreateTask) -> str | None:
    import json, uuid as _uuid
    booking_id = task.booking_data.get("booking_id") or str(_uuid.uuid4())[:8]
    d = task.booking_data
    with rls_cursor(task.property_id) as cur:
        cur.execute(
            """
            INSERT INTO bookings
              (booking_id, property_id, room_type, checkin, checkout, status, amount_inr, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (booking_id) DO NOTHING
            """,
            (
                booking_id,
                task.property_id,
                d.get("room_type", "standard"),
                d.get("checkin"),
                d.get("checkout"),
                d.get("status", "confirmed"),
                d.get("amount_inr", 0),
                d.get("source", "direct"),
            ),
        )
        # Log the event inside the same tenant scope
        cur.execute(
            """
            INSERT INTO events (event_id, property_id, message_id, event_type, payload)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                str(_uuid.uuid4()),
                task.property_id,
                task.message_id,
                "booking_created",
                json.dumps({"booking_id": booking_id}),
            ),
        )
    logger.info("Booking created: %s", booking_id)
    return booking_id


async def _handle_ota_push(task: OTAPushTask) -> None:
    from app.ota.client import push_availability
    import json
    try:
        result = await push_availability(task.push_id, task.payload)
        event_type = "ota_push_ok"
        payload = {"push_id": task.push_id, "result": result}
    except Exception as exc:
        event_type = "ota_push_failed"
        payload = {"push_id": task.push_id, "error": str(exc)}
        logger.warning("OTA push failed for %s: %s", task.push_id, exc)

    loop = asyncio.get_event_loop()
    log_task = EventLogTask(
        property_id=task.property_id,
        event_type=event_type,
        payload=payload,
    )
    await loop.run_in_executor(None, _sync_event_log, log_task)
