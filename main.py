from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncio, time

from pipeline import (
    ingest_metric, get_metric_range,
    list_hosts, list_metrics, get_alerts
)
from explainer import run_full_analysis
from simulator import seed_historical, generate_normal, HOSTS

load_dotenv()

# ── Background analysis loop ──────────────────────────────

analysis_cache = {
    "result":      None,
    "last_run":    0,
    "running":     False,
}

METRICS = [
    "cpu_percent", "memory_percent",
    "db_connections", "request_latency", "error_rate"
]

async def analysis_loop():
    """Runs full analysis every 5 minutes in the background."""
    while True:
        await asyncio.sleep(300)   # 5 minutes
        if not analysis_cache["running"]:
            analysis_cache["running"] = True
            try:
                hosts  = list_hosts()
                result = run_full_analysis(hosts, METRICS)
                analysis_cache["result"]   = result
                analysis_cache["last_run"] = time.time()
                print(f"[analysis] Complete — health: {result['overall_health']}")
            except Exception as e:
                print(f"[analysis] ERROR: {e}")
            finally:
                analysis_cache["running"] = False

# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app):
    print("[server] Seeding historical data...")
    seed_historical(hours=6)
    print("[server] Starting analysis loop...")
    asyncio.create_task(analysis_loop())
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Ingest endpoint ───────────────────────────────────────

@app.post("/ingest")
async def ingest(data: dict):
    """
    Accept a metric datapoint.
    Body: { host, metric, value, timestamp? }
    """
    ingest_metric(
        host=data["host"],
        metric=data["metric"],
        value=float(data["value"]),
        timestamp=data.get("timestamp"),
    )
    return {"status": "ok"}

@app.post("/ingest/batch")
async def ingest_batch_endpoint(data: dict):
    """Accept multiple datapoints at once."""
    from pipeline import ingest_batch
    ingest_batch(data["datapoints"])
    return {"status": "ok", "count": len(data["datapoints"])}

# ── Query endpoints ───────────────────────────────────────

@app.get("/hosts")
def get_hosts():
    return {"hosts": list_hosts()}

@app.get("/metrics")
def get_metrics_for_host(host: str):
    return {"host": host, "metrics": list_metrics(host)}

@app.get("/data")
def get_data(host: str, metric: str, minutes: int = 60):
    points = get_metric_range(host, metric, minutes=minutes)
    return {"host": host, "metric": metric, "points": points}

@app.get("/alerts")
def get_alerts_endpoint(count: int = 20):
    return {"alerts": get_alerts(count)}

# ── Analysis endpoints ────────────────────────────────────

@app.get("/analysis")
def get_analysis():
    """Return cached analysis result."""
    if not analysis_cache["result"]:
        return {
            "status":         "pending",
            "overall_health": "unknown",
            "alerts":         [],
            "forecasts":      [],
            "anomalies":      [],
            "summary":        "Analysis not yet run — check back in 30 seconds.",
            "last_run":       None,
        }
    return {
        "status":   "ok",
        "last_run": analysis_cache["last_run"],
        **analysis_cache["result"],
    }

@app.post("/analysis/run")
async def trigger_analysis(background_tasks: BackgroundTasks):
    """Manually trigger an analysis run."""
    def run():
        if analysis_cache["running"]:
            return
        analysis_cache["running"] = True
        try:
            hosts  = list_hosts()
            result = run_full_analysis(hosts, METRICS)
            analysis_cache["result"]   = result
            analysis_cache["last_run"] = time.time()
        except Exception as e:
            print(f"[analysis] ERROR: {e}")
        finally:
            analysis_cache["running"] = False

    background_tasks.add_task(run)
    return {"status": "triggered"}

@app.get("/health")
def health():
    return {
        "status":       "ok",
        "hosts":        len(list_hosts()),
        "last_analysis": analysis_cache["last_run"],
        "analysis_health": analysis_cache["result"]["overall_health"]
            if analysis_cache["result"] else "pending",
    }

# ── Live simulator endpoint ───────────────────────────────

@app.post("/simulate/tick")
async def simulate_tick():
    """Push one tick of live metrics — call this every few seconds from frontend."""
    import math, random
    t = time.time()
    for host in HOSTS:
        generate_normal(host, t)
    return {"status": "ok", "ts": t}