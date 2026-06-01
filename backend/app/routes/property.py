import json
from fastapi import APIRouter, HTTPException
from app.models import PropertyCreate
from app.database import rls_cursor, raw_cursor

router = APIRouter()


@router.post("/property", status_code=201)
def create_property(config: PropertyCreate):
    """Register a tenant + property_config. Idempotent (upsert)."""
    # Insert into properties (no RLS on this table)
    with raw_cursor() as cur:
        cur.execute(
            """
            INSERT INTO properties (property_id, name, city, total_rooms)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (property_id) DO UPDATE
              SET name = EXCLUDED.name,
                  city = EXCLUDED.city,
                  total_rooms = EXCLUDED.total_rooms
            """,
            (config.property_id, config.name, config.city, config.total_rooms),
        )

    # Insert config into property_configs (RLS-gated)
    cfg_blob = {
        "language": config.language,
        "custom_faqs": config.custom_faqs,
        "name": config.name,
    }
    with rls_cursor(config.property_id) as cur:
        cur.execute(
            """
            INSERT INTO property_configs (property_id, config)
            VALUES (%s, %s)
            ON CONFLICT (property_id) DO UPDATE SET config = EXCLUDED.config
            """,
            (config.property_id, json.dumps(cfg_blob)),
        )

    return {"property_id": config.property_id, "stored": True}


def get_property_config(property_id: str) -> dict:
    """Load property config. Returns {} if not found."""
    with rls_cursor(property_id) as cur:
        cur.execute(
            "SELECT config FROM property_configs WHERE property_id = %s",
            (property_id,),
        )
        row = cur.fetchone()
    if row is None:
        return {}
    cfg = row["config"]
    if isinstance(cfg, str):
        return json.loads(cfg)
    return cfg
