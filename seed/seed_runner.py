"""
Run this once to set up the database schema + seed data.
  python seed/seed_runner.py
Reads DATABASE_URL from .env (in backend/) or the environment.
"""
import os
import sys

# Load .env from backend/ if present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))
except ImportError:
    pass

import psycopg2

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: DATABASE_URL not set. Copy backend/.env.example to backend/.env and fill it in.")
    sys.exit(1)

SEED_DIR = os.path.dirname(__file__)
FILES = [
    os.path.join(SEED_DIR, "schema.sql"),
    os.path.join(SEED_DIR, "data.sql"),
    os.path.join(SEED_DIR, "schema_additions.sql"),
]

conn = psycopg2.connect(DB_URL)
conn.autocommit = True
cur = conn.cursor()

for fpath in FILES:
    print(f"Running {os.path.basename(fpath)}...")
    with open(fpath, "r", encoding="utf-8") as f:
        sql = f.read()
    try:
        cur.execute(sql)
        print(f"  OK")
    except Exception as e:
        print(f"  WARNING: {e}")

cur.close()
conn.close()
print("\nDone. Database ready.")
