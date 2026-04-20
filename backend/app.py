import os
import time
import logging
import random
from contextlib import asynccontextmanager
from typing import Optional

import redis
import redis.sentinel
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import (
    Counter, Histogram, Gauge, Info,
    generate_latest, CONTENT_TYPE_LATEST,
)
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.5, 5.0],
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "In-flight HTTP requests",
    ["method", "endpoint"],
)
REDIS_OPS = Counter(
    "redis_operations_total",
    "Redis operations",
    ["operation", "status"],
)
REDIS_OP_LATENCY = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5],
)
REDIS_KEYS = Gauge("redis_keys_total", "Keys currently stored in Redis")
APP_INFO = Info("app", "Application metadata")

# ---------------------------------------------------------------------------
# Redis connection (supports direct and Sentinel HA)
# ---------------------------------------------------------------------------

def build_redis_client() -> redis.Redis:
    password = os.getenv("REDIS_PASSWORD") or None
    sentinel_hosts_env = os.getenv("REDIS_SENTINEL_HOSTS", "")

    if sentinel_hosts_env:
        sentinel_service = os.getenv("REDIS_SENTINEL_SERVICE", "mymaster")
        hosts = []
        for entry in sentinel_hosts_env.split(","):
            host, port = entry.strip().rsplit(":", 1)
            hosts.append((host, int(port)))
        sentinel = redis.sentinel.Sentinel(
            hosts,
            sentinel_kwargs={"password": password},
            password=password,
            socket_timeout=5,
        )
        logger.info("Connecting via Redis Sentinel: service=%s", sentinel_service)
        return sentinel.master_for(sentinel_service, socket_timeout=5, decode_responses=True)

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    logger.info("Connecting directly to Redis: %s:%d", host, port)
    return redis.Redis(
        host=host,
        port=port,
        password=password,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )


redis_client: Optional[redis.Redis] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client
    APP_INFO.info(
        {
            "version": os.getenv("APP_VERSION", "1.0.0"),
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
    )
    try:
        redis_client = build_redis_client()
        redis_client.ping()
        logger.info("Redis connection OK")
    except Exception as exc:
        logger.warning("Redis unavailable at startup: %s", exc)
    yield
    if redis_client:
        redis_client.close()


app = FastAPI(title="SRE Hello World", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Metrics middleware
# ---------------------------------------------------------------------------

SKIP_METRICS_PATH = {"/metrics", "/health", "/ready"}


@app.middleware("http")
async def track_metrics(request: Request, call_next):
    path = request.url.path
    method = request.method

    if path in SKIP_METRICS_PATH:
        return await call_next(request)

    REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).inc()
    start = time.perf_counter()
    status_code = "500"
    try:
        response = await call_next(request)
        status_code = str(response.status_code)
        return response
    finally:
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(method=method, endpoint=path, status_code=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(duration)
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=path).dec()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class KeyValueBody(BaseModel):
    key: str
    value: str
    ttl: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def require_redis() -> redis.Redis:
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis not initialised")
    return redis_client


def redis_op(operation: str, fn, *args, **kwargs):
    """Run a Redis call, recording latency and counting success/error."""
    start = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
        REDIS_OPS.labels(operation=operation, status="success").inc()
        return result
    except redis.RedisError as exc:
        REDIS_OPS.labels(operation=operation, status="error").inc()
        raise HTTPException(status_code=503, detail=f"Redis error: {exc}") from exc
    finally:
        REDIS_OP_LATENCY.labels(operation=operation).observe(time.perf_counter() - start)


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health():
    status = "healthy"
    redis_status = "disconnected"
    try:
        require_redis().ping()
        redis_status = "connected"
    except Exception:
        status = "degraded"
    return {"status": status, "redis": redis_status}


@app.get("/ready", tags=["ops"])
def ready():
    try:
        require_redis().ping()
        return {"status": "ready"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ---------------------------------------------------------------------------
# Prometheus scrape endpoint
# ---------------------------------------------------------------------------


@app.get("/metrics", tags=["ops"])
def metrics():
    try:
        count = len(require_redis().keys("*"))
        REDIS_KEYS.set(count)
    except Exception:
        pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ---------------------------------------------------------------------------
# Key-Value API
# ---------------------------------------------------------------------------


@app.post("/api/keys", status_code=201, tags=["kv"])
def set_key(body: KeyValueBody):
    r = require_redis()
    if body.ttl:
        redis_op("set", r.setex, body.key, body.ttl, body.value)
    else:
        redis_op("set", r.set, body.key, body.value)
    return {"key": body.key, "value": body.value, "ttl": body.ttl}


@app.get("/api/keys", tags=["kv"])
def list_keys():
    r = require_redis()
    keys = redis_op("list", r.keys, "*")
    result = []
    for key in keys[:100]:
        value = redis_op("get", r.get, key)
        ttl_val = redis_op("ttl", r.ttl, key)
        result.append({"key": key, "value": value, "ttl": ttl_val if ttl_val > 0 else None})
    return {"keys": result, "total": len(keys)}


@app.get("/api/keys/{key}", tags=["kv"])
def get_key(key: str):
    r = require_redis()
    value = redis_op("get", r.get, key)
    if value is None:
        REDIS_OPS.labels(operation="get", status="miss").inc()
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    ttl_val = redis_op("ttl", r.ttl, key)
    return {"key": key, "value": value, "ttl": ttl_val if ttl_val > 0 else None}


@app.delete("/api/keys/{key}", tags=["kv"])
def delete_key(key: str):
    r = require_redis()
    deleted = redis_op("delete", r.delete, key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Key '{key}' not found")
    return {"message": f"Key '{key}' deleted"}


@app.delete("/api/keys", tags=["kv"])
def flush_keys():
    r = require_redis()
    redis_op("flush", r.flushdb)
    return {"message": "All keys deleted"}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@app.get("/api/stats", tags=["kv"])
def stats():
    r = require_redis()
    try:
        info = r.info()
    except redis.RedisError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {
        "connected_clients": info.get("connected_clients", 0),
        "used_memory_human": info.get("used_memory_human", "N/A"),
        "total_commands_processed": info.get("total_commands_processed", 0),
        "keyspace_hits": info.get("keyspace_hits", 0),
        "keyspace_misses": info.get("keyspace_misses", 0),
        "uptime_in_seconds": info.get("uptime_in_seconds", 0),
        "redis_version": info.get("redis_version", "N/A"),
    }


# ---------------------------------------------------------------------------
# SLO simulation endpoints (for demo / load testing)
# ---------------------------------------------------------------------------


@app.get("/api/simulate/slow", tags=["simulate"])
def simulate_slow(delay: float = 1.0):
    """Sleep for `delay` seconds to trigger latency SLO burn."""
    time.sleep(min(delay, 10.0))
    return {"message": f"Responded after {delay}s artificial delay"}


@app.get("/api/simulate/error", tags=["simulate"])
def simulate_error(rate: float = 1.0):
    """Return HTTP 500 with probability `rate` (0.0–1.0) to trigger error-rate SLO burn."""
    if random.random() < min(max(rate, 0.0), 1.0):
        raise HTTPException(status_code=500, detail="Simulated error for SLO demo")
    return {"message": "No error this time"}
