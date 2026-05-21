# 📡 AI-Powered Real-Time Monitoring System

> A real-time system monitoring platform that uses machine learning and AI to predict infrastructure failures before they happen. Instead of alerting after problems occur, this system analyzes patterns in metrics and forecasts issues hours in advance with human-readable explanations powered by Claude AI.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet-purple.svg)](https://anthropic.com)
[![Redis](https://img.shields.io/badge/Redis-7.0+-red.svg)](https://redis.io)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What makes this different

Most monitoring tools tell you **after** something breaks. This system tells you **before**:

```
🚨 CRITICAL — db-01 connections will breach threshold (221/150) in 1 hour

Detail: Database connections on db-01 are at 168 and predicted to hit 305
in 60 minutes, exceeding the 150 limit by 2x with 99% confidence.
Connection pool leak or traffic spike likely.

Recommended action: Immediately check for connection leaks with
SHOW PROCESSLIST, identify and kill long-running queries, restart
application connection pools, and prepare to failover to db-02.
```

---

## ✨ Features

- **Anomaly detection** - Isolation Forest ML model flags unusual metric patterns in real time
- **Time series forecasting** - Linear regression predicts when metrics will breach thresholds
- **AI explanations** - Claude turns raw numbers into actionable on-call alerts
- **Live dashboard** - Real-time metric charts with threshold reference lines
- **Multi-host support** - Monitor unlimited servers simultaneously
- **Redis time series** - Efficient sorted set storage with automatic 24h TTL cleanup
- **REST API** - Full API for ingesting metrics and querying predictions
- **Built-in simulator** - Generates realistic metric data including memory leaks and connection surges for testing

---

## 🏗️ Architecture

```
Your Servers / Applications
       │
       │  POST /ingest  (metrics every 30s)
       ▼
┌─────────────────────────────────────────────┐
│              FastAPI Backend                │
│                                             │
│  pipeline.py                                │
│  ├── Ingest metric datapoints               │
│  ├── Store in Redis sorted sets             │
│  └── Publish to live channels               │
│                                             │
│  detector.py                                │
│  ├── Isolation Forest anomaly detection     │
│  └── Rolling z-score threshold breaches     │
│                                             │
│  forecaster.py                              │
│  ├── Linear regression per metric           │
│  ├── Breach time prediction                 │
│  └── Confidence scoring (R²)                │
│                                             │
│  explainer.py  ←── Claude Sonnet API        │
│  ├── Correlate anomalies + forecasts        │
│  ├── Generate human-readable alerts         │
│  └── Overall health assessment              │
└──────────────┬──────────────────────────────┘
               │
               ▼
        Redis (time series storage)
               │
               ▼
┌─────────────────────────────────────────────┐
│           React Dashboard                   │
│                                             │
│  Overview tab                               │
│  ├── System health banner                   │
│  ├── AI summary paragraph                   │
│  ├── Clickable alert cards with detail      │
│  └── Forecasts table with breach warnings   │
│                                             │
│  Hosts tab                                  │
│  ├── Live metric charts per host            │
│  ├── Threshold reference lines              │
│  └── Metric selector per host               │
└─────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web server | FastAPI + Uvicorn | REST API, metric ingestion |
| AI model | Claude Sonnet (Anthropic) | Alert explanation generation |
| ML models | Scikit-learn Isolation Forest | Anomaly detection |
| Forecasting | Linear regression (NumPy) | Threshold breach prediction |
| Storage | Redis sorted sets | Time series metric storage |
| Dashboard | React 18 + Vite | Real-time frontend |
| Styling | Tailwind CSS | Dashboard design |
| Charts | Recharts | Live metric visualisation |
| Data fetching | TanStack Query | Auto-refresh API calls |

---

## 🚀 Local Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Redis 7+
- An [Anthropic API key](https://console.anthropic.com)

### 1. Clone the repos

```bash
# backend
git clone https://github.com/AbhishekSanthkumar/Ai-Monitoring.git
cd Ai-Monitoring

# dashboard (separate repo)
git clone https://github.com/AbhishekSanthkumar/Ai-Monitoring-Dashboard.git
```

### 2. Backend setup

```bash
cd Ai-Monitoring

# create virtual environment
python -m venv venv

# activate it
# Mac/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# install dependencies
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379
```

### 4. Start Redis

```bash
# Mac (Homebrew)
brew services start redis

# Linux
sudo systemctl start redis

# Windows
# Download from https://redis.io/docs/getting-started/installation/install-redis-on-windows
```

Verify Redis is running:
```bash
redis-cli ping
# should print: PONG
```

### 5. Start the backend

```bash
uvicorn main:app --reload --port 8001
```

On startup the server will automatically seed 6 hours of historical metric data and start a background analysis loop. You should see:

```
[server] Seeding historical data...
[simulator] Done — seeded 2880 datapoints
[server] Starting analysis loop...
INFO: Application startup complete.
```

### 6. Trigger the first analysis

Open a new terminal tab and run:

```bash
curl -X POST http://localhost:8001/analysis/run
```

Wait 30-40 seconds for Claude to process. Then check results:

```bash
curl http://localhost:8001/analysis | python -m json.tool
```

### 7. Start the dashboard

```bash
cd Ai-Monitoring-Dashboard
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

Click **Run analysis** in the dashboard and wait 35 seconds, you should see the health status update with AI-generated alerts.

---

## ☁️ Deployment

### Backend on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Select `Ai-Monitoring`
3. Click **+ New** → **Database** → **Add Redis**
   - Railway automatically sets `REDIS_URL` for your app
4. Go to your app service → **Variables** tab → add:
   ```
   ANTHROPIC_API_KEY = sk-ant-...
   ```
5. Railway uses the `Procfile` to start the server:
   ```
   web: uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Click **Deploy** - your API will be live at:
   ```
   https://your-project.up.railway.app
   ```

### Dashboard on Vercel

1. Update the API URL in `Ai-Monitoring-Dashboard/src/App.jsx`:
   ```js
   const API = "https://your-railway-url.up.railway.app"
   ```
2. Commit and push the change
3. Go to [vercel.com](https://vercel.com) → **New Project** → import `Ai-Monitoring-Dashboard`
4. Vercel auto-detects Vite — click **Deploy**
5. Your dashboard will be live at:
   ```
   https://Ai-Monitoring-Dashboard.vercel.app
   ```

### Update CORS after deployment

Once you have your Vercel URL, update `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-monitoring-dashboard.vercel.app",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 📡 Sending Real Metrics

To monitor your own servers, send metrics to the `/ingest` endpoint:

```bash
# single metric
curl -X POST https://your-api.up.railway.app/ingest \
  -H "Content-Type: application/json" \
  -d '{"host": "my-server-01", "metric": "cpu_percent", "value": 67.3}'

# batch metrics
curl -X POST https://your-api.up.railway.app/ingest/batch \
  -H "Content-Type: application/json" \
  -d '{
    "datapoints": [
      {"host": "my-server-01", "metric": "cpu_percent", "value": 67.3},
      {"host": "my-server-01", "metric": "memory_percent", "value": 84.1},
      {"host": "my-server-01", "metric": "db_connections", "value": 43}
    ]
  }'
```

### Python agent example

Add this to any Python service to send metrics automatically:

```python
import psutil, requests, time

API = "https://your-api.up.railway.app"
HOST = "my-server-01"

while True:
    requests.post(f"{API}/ingest/batch", json={"datapoints": [
        {"host": HOST, "metric": "cpu_percent",    "value": psutil.cpu_percent()},
        {"host": HOST, "metric": "memory_percent", "value": psutil.virtual_memory().percent},
    ]})
    time.sleep(30)
```

---

## 📁 Project Structure

```
Ai-Monitoring/
├── main.py          # FastAPI app, API endpoints, background analysis loop
├── pipeline.py      # Redis time series ingestion and querying
├── detector.py      # Isolation Forest anomaly detection
├── forecaster.py    # Linear regression forecasting with breach prediction
├── explainer.py     # Claude AI alert generation
├── simulator.py     # Realistic metric simulation for testing
├── Procfile         # Railway deployment config
├── requirements.txt # Python dependencies
└── .env             # Secrets (never commit this)

monitoring-dashboard/
├── src/
│   ├── App.jsx      # Full dashboard — health, alerts, charts
│   └── index.css    # Tailwind import
├── vite.config.js
└── package.json
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a single metric datapoint |
| `POST` | `/ingest/batch` | Ingest multiple datapoints at once |
| `GET` | `/hosts` | List all monitored hosts |
| `GET` | `/metrics?host=X` | List metrics for a host |
| `GET` | `/data?host=X&metric=Y&minutes=60` | Fetch time series data |
| `GET` | `/analysis` | Get latest AI analysis and alerts |
| `POST` | `/analysis/run` | Trigger a new analysis immediately |
| `GET` | `/alerts` | Fetch recent alerts from Redis stream |
| `GET` | `/health` | Server health check |
| `POST` | `/simulate/tick` | Push one tick of simulated metrics |

---

## 🧠 How the AI predictions work

**Step 1 — Ingest:** Metrics arrive via REST API and are stored in Redis sorted sets with timestamps as scores. This gives O(log n) range queries by time window.

**Step 2 — Detect:** Every analysis run, Isolation Forest scans the last 60 minutes of each metric. Points with anomaly scores below -0.1 are flagged. The algorithm learns what normal looks like for each metric.

**Step 3 — Forecast:** Linear regression fits a trend line to the last 6 hours of data. The slope predicts the value N hours from now. R² gives confidence. If the predicted value exceeds the threshold, a breach is flagged with the estimated time.

**Step 4 — Explain:** Concerning forecasts and anomalies are sent to Claude with a structured prompt. Claude correlates signals across metrics and hosts, identifies root causes, and generates specific on-call alerts with recommended actions.

**Step 5 — Alert:** Results are cached and served via the `/analysis` endpoint. The dashboard polls every 60 seconds and displays health status, alerts, and forecasts in real time.

---

## 🗺️ Roadmap

- [x] Redis time series ingestion pipeline
- [x] Isolation Forest anomaly detection
- [x] Linear regression breach forecasting
- [x] Claude AI alert explanations
- [x] React real-time dashboard
- [x] Multi-host support
- [ ] WebSocket live updates (no polling)
- [ ] Slack / PagerDuty alert routing
- [ ] Custom threshold configuration per metric
- [ ] LSTM neural network for seasonal forecasting
- [ ] Kubernetes metrics integration
- [ ] Historical incident correlation

---

## 🤝 Contributing

Pull requests are welcome. For major changes please open an issue first.

---

## 📄 License

[MIT](LICENSE)

---

## 👤 Author

**Abhishek Santhkumar**
Built as a portfolio project demonstrating distributed systems, machine learning, time series analysis, and AI integration.

> ⭐ If this project helped you, please give it a star on GitHub!
