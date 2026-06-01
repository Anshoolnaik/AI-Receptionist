"""
Mock OTA client with exponential backoff retry on 429/500.
Idempotent: same push_id is a no-op on the OTA server side.
"""
import asyncio
import logging
import httpx

from app.config import OTA_BASE_URL

logger = logging.getLogger(__name__)

MAX_RETRIES = 6
BASE_DELAY_S = 1.0


async def push_availability(push_id: str, payload: dict) -> dict:
    """
    POST /availability to the mock OTA.
    Retries on 429 (using Retry-After header) and 500 (exponential backoff).
    Raises OTAExhaustedError after MAX_RETRIES failures.
    """
    url = f"{OTA_BASE_URL}/availability"
    body = {"push_id": push_id, **payload}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(MAX_RETRIES):
            try:
                resp = await client.post(url, json=body)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "duplicate_ignored":
                        logger.info("OTA: duplicate push_id %s (idempotent no-op)", push_id)
                    else:
                        logger.info("OTA push accepted: %s", push_id)
                    return data

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", BASE_DELAY_S * (2 ** attempt)))
                    logger.warning(
                        "OTA 429 rate-limited. push_id=%s attempt=%d wait=%ds",
                        push_id, attempt, retry_after
                    )
                    await asyncio.sleep(retry_after)
                    continue

                if resp.status_code == 500:
                    wait = BASE_DELAY_S * (2 ** attempt)
                    logger.warning(
                        "OTA 500 upstream error. push_id=%s attempt=%d wait=%.1fs",
                        push_id, attempt, wait
                    )
                    await asyncio.sleep(wait)
                    continue

                # Unexpected status
                raise OTAError(f"Unexpected OTA response: {resp.status_code} — {resp.text}")

            except httpx.RequestError as exc:
                wait = BASE_DELAY_S * (2 ** attempt)
                logger.warning("OTA request error attempt=%d: %s — retrying in %.1fs", attempt, exc, wait)
                await asyncio.sleep(wait)

    raise OTAExhaustedError(
        f"OTA push exhausted after {MAX_RETRIES} attempts for push_id={push_id}"
    )


class OTAError(Exception):
    pass


class OTAExhaustedError(OTAError):
    pass
