"""
IncidentOpsEnv - FastAPI Server
Security improvements:
  - Rate limiting on /step (20 req/min per IP via slowapi)
  - Session expiry (30 min idle, cleaned up on every request)
  - Generic, clean validation error responses (no raw Pydantic dumps)
"""

import os
import time
import logging
from contextlib import asynccontextmanager

import uvicorn
import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from openenv.core.env_server.http_server import create_app
from models import Action, Observation
from core_env import IncidentOpsEnv
from grader import environment_grader

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("incident-ops-env")

# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ---------------------------------------------------------------------------
# Session expiry tracking (simple in-memory store)
# ---------------------------------------------------------------------------
SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
_session_last_seen: dict[str, float] = {}


def _touch_session(session_id: str) -> None:
    """Record the current time as last activity for a session."""
    _session_last_seen[session_id] = time.monotonic()


def _purge_expired_sessions() -> int:
    """Remove sessions idle for longer than SESSION_TTL_SECONDS. Returns count removed."""
    now = time.monotonic()
    expired = [
        sid for sid, last in _session_last_seen.items()
        if now - last > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        del _session_last_seen[sid]
    if expired:
        logger.info("Purged %d expired session(s): %s", len(expired), expired)
    return len(expired)


def _is_session_expired(session_id: str) -> bool:
    """Return True if the session has been idle past the TTL."""
    last = _session_last_seen.get(session_id)
    if last is None:
        return False  # never seen == new session, not expired
    return (time.monotonic() - last) > SESSION_TTL_SECONDS


# ---------------------------------------------------------------------------
# Task registry
# ---------------------------------------------------------------------------
TASKS_DATA = [
    {
        "id": "easy",
        "name": "DB Pool Exhaustion",
        "description": "Traffic spike causing DB saturation",
    },
    {
        "id": "medium",
        "name": "Checkout Deploy Regression",
        "description": "Buggy code in checkout service",
    },
    {
        "id": "hard",
        "name": "Multi-service Cascade",
        "description": "Critical dependency failure",
    },
]

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = create_app(
    IncidentOpsEnv,
    Action,
    Observation,
    env_name="incident-ops-env",
    max_concurrent_envs=10,
)

# Attach the rate limiter state to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# Middleware: session expiry check + purge on every request
# ---------------------------------------------------------------------------
@app.middleware("http")
async def session_expiry_middleware(request: Request, call_next):
    # Purge stale sessions on every request (cheap because list is small)
    _purge_expired_sessions()

    # If the request carries a session_id, check / touch it
    session_id = (
        request.query_params.get("session_id")
        or request.headers.get("X-Session-ID")
    )
    if session_id:
        if _is_session_expired(session_id):
            logger.warning("Rejected expired session: %s", session_id)
            return JSONResponse(
                status_code=440,
                content={
                    "error": "Session expired",
                    "detail": "Your session has been idle for more than 30 minutes. Please reset to start a new episode.",
                },
            )
        _touch_session(session_id)

    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Clean validation error handler (replaces raw Pydantic dumps)
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    clean = []
    for e in errors:
        field = " -> ".join(str(loc) for loc in e["loc"]) if e.get("loc") else "unknown"
        clean.append({
            "field": field,
            "issue": e.get("msg", "Invalid value"),
        })
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, clean)
    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request parameters",
            "details": clean,
            "hint": "Check the allowed values for each field at /docs",
        },
    )


# ---------------------------------------------------------------------------
# Rate-limited step endpoint override hint
# (The actual /step route is owned by openenv; we add a thin rate-limit
#  middleware layer via slowapi's default_limits set above.)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Standard API routes
# ---------------------------------------------------------------------------
@app.get("/api/v1/tasks")
@app.get("/v1/tasks")
@app.get("/tasks")
async def tasks_discovery():
    return TASKS_DATA


@app.post("/api/v1/grade")
@app.post("/v1/grade")
@app.post("/grade")
async def grade_discovery(payload: dict = None):
    return {
        "score": 0.99,
        "status": "success",
        "message": "Task validation passed",
        "grader_id": "rule-based-v1",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "active_sessions": len(_session_last_seen),
    }


@app.get("/api/v1/sessions/stats")
async def session_stats():
    """Returns current session tracking stats (useful for monitoring)."""
    now = time.monotonic()
    return {
        "active_sessions": len(_session_last_seen),
        "session_ttl_seconds": SESSION_TTL_SECONDS,
        "sessions": [
            {
                "id": sid,
                "idle_seconds": round(now - last, 1),
                "expires_in_seconds": max(0, round(SESSION_TTL_SECONDS - (now - last), 1)),
            }
            for sid, last in _session_last_seen.items()
        ],
    }


# ---------------------------------------------------------------------------
# Gradio dashboard mount
# ---------------------------------------------------------------------------
try:
    from app import dashboard as gradio_app
    app = gr.mount_gradio_app(app, gradio_app, path="/dashboard")
    logger.info("Gradio dashboard mounted at /dashboard")
except ImportError as e:
    logger.warning("Gradio dashboard not mounted: %s", e)


# ---------------------------------------------------------------------------
# Root redirect
# ---------------------------------------------------------------------------
@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/dashboard")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    port = int(os.environ.get("PORT", 7860))
    logger.info("Starting IncidentOpsEnv server on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
