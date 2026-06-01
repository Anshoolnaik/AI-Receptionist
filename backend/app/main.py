"""
Engineering Capstone — Multi-Tenant Receptionist + Data Assistant
FastAPI application entry point.
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_pool, close_pool
from app.queue.worker import queue_worker
from app.assistant.rag import build_index
from app.classifier.classify import get_p50_ms, get_p95_ms

from app.routes.property import router as property_router
from app.routes.message import router as message_router
from app.routes.lifecycle import router as lifecycle_router
from app.routes.ask import router as ask_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting up...")

    # 1. Init DB connection pool
    init_pool(minconn=1, maxconn=10)
    logger.info("DB pool ready")

    # 2. Build RAG index from kb/ files (once at startup)
    build_index()

    # 3. Start async queue worker
    queue: asyncio.Queue = asyncio.Queue()
    app.state.queue = queue
    worker_task = asyncio.create_task(queue_worker(queue))
    logger.info("Queue worker started")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    await queue.join()        # drain remaining tasks
    worker_task.cancel()
    close_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Hotel Capstone API",
    description="Multi-tenant receptionist + data assistant",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(property_router)
app.include_router(message_router)
app.include_router(lifecycle_router)
app.include_router(ask_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    """Classification latency stats (P50/P95 in ms)."""
    return {
        "classify_p50_ms": get_p50_ms(),
        "classify_p95_ms": get_p95_ms(),
    }
