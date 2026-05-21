import redis, json, time, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Connection ────────────────────────────────────────────

r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

# ── Keys ──────────────────────────────────────────────────

def metric_key(host: str, metric: str) -> str:
    """Redis key for a time series: metrics:{host}:{metric}"""
    return f"metrics:{host}:{metric}"

def alert_key() -> str:
    return "alerts:stream"

# ── Write ─────────────────────────────────────────────────

def ingest_metric(host: str, metric: str, value: float, timestamp: float = None):
    """
    Store a single metric data point.
    Uses Redis sorted set — timestamp is the score, value is the member.
    This gives us O(log n) range queries by time.
    """
    ts = timestamp or time.time()
    key = metric_key(host, metric)

    # store as JSON so we can add metadata later
    entry = json.dumps({"value": value, "ts": ts})
    r.zadd(key, {entry: ts})

    # keep only last 24 hours of data per metric
    cutoff = ts - (24 * 60 * 60)
    r.zremrangebyscore(key, "-inf", cutoff)

    # publish to channel so live dashboard gets instant updates
    r.publish(f"live:{host}:{metric}", json.dumps({
        "host": host, "metric": metric, "value": value, "ts": ts
    }))

def ingest_batch(datapoints: list[dict]):
    """Ingest multiple metrics at once using a pipeline for speed."""
    pipe = r.pipeline()
    for dp in datapoints:
        ts = dp.get("ts") or time.time()
        key = metric_key(dp["host"], dp["metric"])
        entry = json.dumps({"value": dp["value"], "ts": ts})
        pipe.zadd(key, {entry: ts})
        cutoff = ts - (24 * 60 * 60)
        pipe.zremrangebyscore(key, "-inf", cutoff)
    pipe.execute()

# ── Read ──────────────────────────────────────────────────

def get_metric_range(
    host: str,
    metric: str,
    minutes: int = 60,
) -> list[dict]:
    """Fetch the last N minutes of data for a metric."""
    key = metric_key(host, metric)
    now = time.time()
    cutoff = now - (minutes * 60)

    raw = r.zrangebyscore(key, cutoff, "+inf", withscores=True)
    points = []
    for entry, score in raw:
        data = json.loads(entry)
        points.append({
            "ts": data["ts"],
            "value": data["value"],
            "datetime": datetime.fromtimestamp(data["ts"]).isoformat(),
        })
    return points

def get_latest_value(host: str, metric: str) -> float | None:
    """Get the most recent value for a metric."""
    key = metric_key(host, metric)
    raw = r.zrange(key, -1, -1)
    if not raw:
        return None
    return json.loads(raw[0])["value"]

def list_hosts() -> list[str]:
    """Return all hosts that have sent metrics."""
    keys = r.keys("metrics:*:*")
    hosts = set()
    for k in keys:
        parts = k.decode().split(":")
        if len(parts) >= 3:
            hosts.add(parts[1])
    return sorted(list(hosts))

def list_metrics(host: str) -> list[str]:
    """Return all metric names for a host."""
    keys = r.keys(f"metrics:{host}:*")
    metrics = []
    for k in keys:
        parts = k.decode().split(":")
        if len(parts) >= 3:
            metrics.append(parts[2])
    return sorted(metrics)

# ── Alerts ────────────────────────────────────────────────

def save_alert(host: str, metric: str, severity: str, message: str, predicted_at: str = None):
    """Save a prediction alert to Redis stream."""
    alert = {
        "host": host,
        "metric": metric,
        "severity": severity,
        "message": message,
        "predicted_at": predicted_at or "",
        "created_at": datetime.now().isoformat(),
    }
    r.xadd("alerts:stream", {k: v for k, v in alert.items()})
    # keep only last 100 alerts
    r.xtrim("alerts:stream", maxlen=100)

def get_alerts(count: int = 20) -> list[dict]:
    """Fetch recent alerts from Redis stream."""
    raw = r.xrevrange("alerts:stream", count=count)
    alerts = []
    for msg_id, fields in raw:
        alert = {k.decode(): v.decode() for k, v in fields.items()}
        alert["id"] = msg_id.decode()
        alerts.append(alert)
    return alerts