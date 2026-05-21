import time, math, random
from pipeline import ingest_metric

# ── Metric profiles ───────────────────────────────────────

def cpu_usage(t: float, anomaly: bool = False) -> float:
    """Simulates CPU with daily cycle + random noise."""
    base = 45 + 20 * math.sin(2 * math.pi * t / 86400)
    noise = random.gauss(0, 5)
    spike = random.uniform(60, 95) if anomaly else 0
    return max(0, min(100, base + noise + spike))

def memory_usage(t: float, trend: float = 0) -> float:
    """Simulates gradual memory leak with trend parameter."""
    base = 60 + trend * (t % 3600) / 3600
    noise = random.gauss(0, 3)
    return max(0, min(100, base + noise))

def db_connections(t: float, spike: bool = False) -> float:
    """Simulates database connection pool usage."""
    base = 30 + 15 * math.sin(2 * math.pi * t / 3600)
    noise = random.gauss(0, 4)
    surge = random.uniform(40, 80) if spike else 0
    return max(0, min(200, base + noise + surge))

def request_latency(t: float, degraded: bool = False) -> float:
    """Simulates API response time in milliseconds."""
    base = 120 + 30 * math.sin(2 * math.pi * t / 7200)
    noise = random.gauss(0, 15)
    extra = random.uniform(200, 800) if degraded else 0
    return max(10, base + noise + extra)

def error_rate(t: float, incident: bool = False) -> float:
    """Simulates error rate as percentage."""
    base = 0.5 + random.gauss(0, 0.2)
    surge = random.uniform(5, 25) if incident else 0
    return max(0, base + surge)

# ── Scenarios ─────────────────────────────────────────────

HOSTS = ["web-01", "web-02", "db-01", "cache-01"]

def generate_normal(host: str, t: float):
    """Generate normal healthy metrics for a host."""
    ingest_metric(host, "cpu_percent",      cpu_usage(t))
    ingest_metric(host, "memory_percent",   memory_usage(t))
    ingest_metric(host, "request_latency",  request_latency(t))
    ingest_metric(host, "error_rate",       error_rate(t))
    if "db" in host:
        ingest_metric(host, "db_connections", db_connections(t))

def generate_memory_leak(host: str, t: float, severity: float = 1.0):
    """Simulate a gradual memory leak — classic pre-incident pattern."""
    ingest_metric(host, "cpu_percent",     cpu_usage(t))
    ingest_metric(host, "memory_percent",  memory_usage(t, trend=severity * 25))
    ingest_metric(host, "request_latency", request_latency(t))
    ingest_metric(host, "error_rate",      error_rate(t))

def generate_db_saturation(host: str, t: float):
    """Simulate DB connection pool filling up."""
    ingest_metric(host, "cpu_percent",     cpu_usage(t))
    ingest_metric(host, "memory_percent",  memory_usage(t))
    ingest_metric(host, "request_latency", request_latency(t, degraded=True))
    ingest_metric(host, "db_connections",  db_connections(t, spike=True))
    ingest_metric(host, "error_rate",      error_rate(t))

# ── Runner ────────────────────────────────────────────────

def seed_historical(hours: int = 6):
    """
    Seed Redis with historical data so the dashboard
    has something to show immediately on startup.
    """
    print(f"[simulator] Seeding {hours}h of historical data...")
    now = time.time()
    interval = 30  # one datapoint every 30 seconds
    steps = int(hours * 3600 / interval)

    for i in range(steps):
        t = now - (steps - i) * interval

        for host in HOSTS:
            if host == "db-01":
                # db-01 has a memory leak starting 2 hours ago
                leak_start = now - 2 * 3600
                severity = max(0, (t - leak_start) / 3600) if t > leak_start else 0
                generate_memory_leak(host, t, severity)
            elif host == "web-02":
                # web-02 has occasional DB connection spikes
                spike = random.random() < 0.05
                generate_db_saturation(host, t) if spike else generate_normal(host, t)
            else:
                generate_normal(host, t)

        if i % 100 == 0:
            pct = int(i / steps * 100)
            print(f"[simulator] {pct}% complete...")

    print(f"[simulator] Done — seeded {steps * len(HOSTS)} datapoints")

def run_live(interval: float = 5.0):
    """Stream live metrics every N seconds."""
    print(f"[simulator] Streaming live metrics every {interval}s — Ctrl+C to stop")
    try:
        while True:
            t = time.time()
            for host in HOSTS:
                generate_normal(host, t)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[simulator] Stopped")

if __name__ == "__main__":
    seed_historical(hours=6)
    run_live(interval=5)