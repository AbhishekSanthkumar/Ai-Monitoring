import numpy as np
import pandas as pd
from prophet import Prophet
from pipeline import get_metric_range
from dataclasses import dataclass
import warnings
warnings.filterwarnings("ignore")   # Prophet is noisy

# ── Data model ────────────────────────────────────────────

@dataclass
class Forecast:
    host: str
    metric: str
    current_value: float
    predicted_value: float    # value at prediction horizon
    predicted_at: str         # when we predict it will happen
    hours_ahead: int
    trend: str                # rising | falling | stable
    will_breach: bool         # will it exceed threshold?
    threshold: float
    confidence: float         # 0-1

# ── Thresholds ────────────────────────────────────────────
# these are the values we care about breaching

THRESHOLDS = {
    "cpu_percent":      85.0,
    "memory_percent":   90.0,
    "db_connections":   150.0,
    "request_latency":  500.0,
    "error_rate":       5.0,
}

# ── Core forecaster ───────────────────────────────────────

def forecast_metric(
    host: str,
    metric: str,
    hours_ahead: int = 6,
    minutes_history: int = 360,
) -> Forecast | None:
    """
    Forecasts a metric using linear regression for trending metrics
    and Prophet for stable/seasonal ones.
    """
    points = get_metric_range(host, metric, minutes=minutes_history)
    if len(points) < 30:
        return None

    df = pd.DataFrame(points)
    df["ds"] = pd.to_datetime(df["datetime"])
    df["y"]  = df["value"]
    df = df.sort_values("ds")

    values  = df["y"].values
    times   = np.arange(len(values))

    # fit a simple linear regression
    slope, intercept = np.polyfit(times, values, 1)

    # predict N hours ahead
    # each point is 30s apart so 1 hour = 120 points
    points_per_hour = 120
    future_idx      = len(values) + (hours_ahead * points_per_hour)
    predicted_value = slope * future_idx + intercept

    current_value = float(values[-1])
    threshold     = THRESHOLDS.get(metric, float("inf"))

    # determine trend from slope
    # slope is per-datapoint, convert to per-hour
    slope_per_hour = slope * points_per_hour
    if slope_per_hour > 0.5:    trend = "rising"
    elif slope_per_hour < -0.5: trend = "falling"
    else:                       trend = "stable"

    # confidence from R² of the linear fit
    predicted_historical = slope * times + intercept
    ss_res = np.sum((values - predicted_historical) ** 2)
    ss_tot = np.sum((values - np.mean(values)) ** 2)
    r2     = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    confidence = round(max(0, min(r2, 0.99)), 2)

    # predicted_at timestamp
    from datetime import datetime, timedelta
    predicted_at = (datetime.now() + timedelta(hours=hours_ahead)).isoformat()

    # will it breach threshold?
    # check every hour between now and horizon
    will_breach = False
    breach_in_hours = None
    for h in range(1, hours_ahead + 1):
        idx = len(values) + (h * points_per_hour)
        val = slope * idx + intercept
        if val >= threshold:
            will_breach = True
            breach_in_hours = h
            break

    return Forecast(
        host=host,
        metric=metric,
        current_value=round(current_value, 2),
        predicted_value=round(float(predicted_value), 2),
        predicted_at=predicted_at,
        hours_ahead=breach_in_hours or hours_ahead,
        trend=trend,
        will_breach=will_breach,
        threshold=threshold,
        confidence=confidence,
    )

# ── Scan for concerning forecasts ─────────────────────────

def scan_forecasts(
    hosts: list[str],
    metrics: list[str],
    hours_ahead: int = 6,
) -> list[dict]:
    """
    Run forecasts across all host/metric combos.
    Return only ones that are rising or will breach threshold.
    """
    concerning = []

    for host in hosts:
        for metric in metrics:
            print(f"[forecast] {host} / {metric}...")
            fc = forecast_metric(host, metric, hours_ahead=hours_ahead)
            if fc is None:
                continue

            # only surface rising trends or threshold breaches
            if fc.trend == "rising" or fc.will_breach:
                concerning.append({
                    "host":            fc.host,
                    "metric":          fc.metric,
                    "current_value":   fc.current_value,
                    "predicted_value": fc.predicted_value,
                    "predicted_at":    fc.predicted_at,
                    "hours_ahead":     fc.hours_ahead,
                    "trend":           fc.trend,
                    "will_breach":     fc.will_breach,
                    "threshold":       fc.threshold,
                    "confidence":      fc.confidence,
                })

    return concerning