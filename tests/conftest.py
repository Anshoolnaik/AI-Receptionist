"""
Pytest fixtures for the e2e test suite.
Tests run against a live backend (local or deployed).
Set BACKEND_URL env var to point to a deployed instance.
"""
import os
import pytest
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BACKEND_URL


@pytest.fixture(scope="session")
def client(base_url: str):
    with httpx.Client(base_url=base_url, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def seed_properties(client):
    """Ensure both hotel_a and hotel_b are registered before tests run."""
    for prop in [
        {
            "property_id": "hotel_a",
            "name": "Hotel Surya (Varanasi)",
            "city": "Varanasi",
            "total_rooms": 24,
            "language": "hi",
            "custom_faqs": [
                {"q": "checkout time", "a": "11 AM"},
                {"q": "wifi", "a": "Free WiFi, password at reception"},
                {"q": "parking", "a": "Free on-site parking"},
            ],
        },
        {
            "property_id": "hotel_b",
            "name": "Coastal Stay PG (Bengaluru)",
            "city": "Bengaluru",
            "total_rooms": 40,
            "language": "en",
            "custom_faqs": [
                {"q": "rent", "a": "₹9,500/month sharing, ₹14,000 single"},
                {"q": "food", "a": "Veg/non-veg mess included"},
                {"q": "deposit", "a": "Two months refundable"},
            ],
        },
    ]:
        r = client.post("/property", json=prop)
        assert r.status_code in (200, 201), f"seed_properties failed: {r.text}"
