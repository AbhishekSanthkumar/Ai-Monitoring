import os
from anthropic import Anthropic
from dotenv import load_dotenv
from forecaster import Forecast
from detector import Anomaly
from pipeline import save_alert

load_dotenv()

client = Anthropic()

# ── Prompt builder ────────────────────────────────────────

def build_forecast_prompt(forecasts: list[dict], anomalies: list[dict]) -> str:
    forecast_text = ""
    for f in forecasts:
        status = "WILL BREACH THRESHOLD" if f["will_breach"] else "trending up"
        forecast_text += f"""
- {f['host']} / {f['metric']}
  Current: {f['current_value']} | Predicted: {f['predicted_value']} in {f['hours_ahead']}h
  Threshold: {f['threshold']} | Status: {status}
  Confidence: {f['confidence']}
"""

    anomaly_text = ""
    for a in anomalies[:10]:  # cap at 10 to stay within context
        anomaly_text += f"""
- {a['host']} / {a['metric']}
  Value: {a['value']} | Expected: {a['expected_range']} | Severity: {a['severity']}
"""

    return f"""You are an expert site reliability engineer analyzing system metrics.

Based on the following forecasts and anomalies, generate actionable alerts.
Be specific — name exact metrics, values, timeframes, and recommended actions.
Write like you are paging an on-call engineer at 3am. Be concise and direct.

FORECASTS (metrics predicted to breach thresholds):
{forecast_text}

RECENT ANOMALIES:
{anomaly_text if anomaly_text else "None detected"}

Respond ONLY with a JSON object in this exact shape:
{{
  "alerts": [
    {{
      "host": "hostname",
      "metric": "metric_name",
      "severity": "critical|high|medium",
      "headline": "One line summary — what will happen and when",
      "detail": "2-3 sentences explaining the pattern, predicted impact, and recommended action",
      "predicted_at": "approximate time this will breach e.g. in 2 hours",
      "recommended_action": "specific thing to do right now"
    }}
  ],
  "overall_health": "healthy|degraded|critical",
  "summary": "One paragraph executive summary of system health"
}}

Only generate alerts for genuine concerns. If everything looks healthy say so."""

# ── Main explainer ────────────────────────────────────────

def explain_predictions(
    forecasts: list[dict],
    anomalies: list[dict],
) -> dict:
    """
    Send forecast + anomaly data to Claude.
    Returns structured alerts with human-readable explanations.
    """
    if not forecasts and not anomalies:
        return {
            "alerts": [],
            "overall_health": "healthy",
            "summary": "All systems operating within normal parameters."
        }

    prompt = build_forecast_prompt(forecasts, anomalies)

    print("[explainer] Sending to Claude...")
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    print(f"[explainer] Got response ({len(raw)} chars)")

    # parse JSON response
    import re, json
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        return {
            "alerts": [],
            "overall_health": "unknown",
            "summary": raw,
        }

    # save alerts to Redis stream
    for alert in result.get("alerts", []):
        save_alert(
            host=alert.get("host", "unknown"),
            metric=alert.get("metric", "unknown"),
            severity=alert.get("severity", "medium"),
            message=alert.get("headline", ""),
            predicted_at=alert.get("predicted_at", ""),
        )

    return result

# ── Full analysis pipeline ────────────────────────────────

def run_full_analysis(hosts: list[str], metrics: list[str]) -> dict:
    """
    Run forecasts + anomaly detection + Claude explanation
    in one shot. This is what the API will call every 5 minutes.
    """
    from forecaster import scan_forecasts
    from detector import scan_all_hosts

    print("[analysis] Running forecasts...")
    forecasts = scan_forecasts(hosts, metrics, hours_ahead=6)

    print("[analysis] Running anomaly detection...")
    detection = scan_all_hosts(hosts, metrics)
    anomalies = detection["anomalies"]

    print(f"[analysis] Found {len(forecasts)} concerning forecasts, {len(anomalies)} anomalies")

    print("[analysis] Getting Claude explanations...")
    result = explain_predictions(forecasts, anomalies)

    return {
        "forecasts":      forecasts,
        "anomalies":      anomalies[:20],
        "alerts":         result.get("alerts", []),
        "overall_health": result.get("overall_health", "unknown"),
        "summary":        result.get("summary", ""),
    }