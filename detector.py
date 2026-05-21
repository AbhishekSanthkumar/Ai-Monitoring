import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from pipeline import get_metric_range, get_latest_value
from dataclasses import dataclass

# ── Data model ────────────────────────────────────────────

@dataclass
class Anomaly:
    host: str
    metric: str
    value: float
    expected_range: tuple[float, float]
    severity: str        # low | medium | high | critical
    score: float         # isolation forest anomaly score
    timestamp: str

# ── Helpers ───────────────────────────────────────────────

def to_dataframe(points: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(points)
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("ts")
    return df

def severity_from_score(score: float) -> str:
    """
    Isolation Forest returns scores between -1 and 1.
    More negative = more anomalous.
    """
    if score < -0.3:   return "critical"
    if score < -0.2:   return "high"
    if score < -0.1:   return "medium"
    return "low"

# ── Isolation Forest detector ─────────────────────────────

def detect_anomalies(
    host: str,
    metric: str,
    minutes: int = 60,
    contamination: float = 0.05,
) -> list[Anomaly]:
    """
    Runs Isolation Forest on recent metric data.
    contamination = expected % of anomalous points (5% default).
    """
    points = get_metric_range(host, metric, minutes=minutes)
    if len(points) < 20:
        return []   # not enough data to detect anomalies reliably

    df = to_dataframe(points)
    values = df["value"].values.reshape(-1, 1)

    # scale so the model isn't thrown off by metric magnitude
    scaler = StandardScaler()
    scaled = scaler.fit_transform(values)

    model = IsolationForest(
        contamination=contamination,
        random_state=42,
        n_estimators=100,
    )
    model.fit(scaled)

    scores  = model.score_samples(scaled)
    labels  = model.predict(scaled)   # -1 = anomaly, 1 = normal

    # expected range = mean ± 2 std
    mean = float(np.mean(values))
    std  = float(np.std(values))
    expected = (round(mean - 2*std, 2), round(mean + 2*std, 2))

    anomalies = []
    for i, (label, score) in enumerate(zip(labels, scores)):
        if label == -1:
            anomalies.append(Anomaly(
                host=host,
                metric=metric,
                value=round(float(values[i][0]), 2),
                expected_range=expected,
                severity=severity_from_score(score),
                score=round(float(score), 4),
                timestamp=df["datetime"].iloc[i].isoformat(),
            ))

    return anomalies

# ── Rolling statistics detector ───────────────────────────

def detect_threshold_breach(
    host: str,
    metric: str,
    minutes: int = 30,
) -> dict | None:
    """
    Simpler detector — checks if recent values are
    consistently above/below rolling average.
    Good for catching slow-burn issues like memory leaks.
    """
    points = get_metric_range(host, metric, minutes=minutes)
    if len(points) < 10:
        return None

    df = to_dataframe(points)
    values = df["value"].values

    # rolling mean of last 10 points vs overall mean
    recent_mean  = float(np.mean(values[-10:]))
    overall_mean = float(np.mean(values))
    overall_std  = float(np.std(values))

    if overall_std == 0:
        return None

    # z-score of recent window vs historical
    z_score = (recent_mean - overall_mean) / overall_std

    if abs(z_score) < 1.5:
        return None   # within normal range

    direction = "above" if z_score > 0 else "below"
    severity  = "critical" if abs(z_score) > 3 else \
                "high"     if abs(z_score) > 2 else "medium"

    return {
        "host":          host,
        "metric":        metric,
        "recent_mean":   round(recent_mean, 2),
        "overall_mean":  round(overall_mean, 2),
        "z_score":       round(z_score, 2),
        "direction":     direction,
        "severity":      severity,
    }

# ── Scan all hosts ────────────────────────────────────────

def scan_all_hosts(hosts: list[str], metrics: list[str]) -> dict:
    """Run both detectors across every host/metric combination."""
    results = {
        "anomalies":  [],
        "breaches":   [],
        "scanned":    0,
    }

    for host in hosts:
        for metric in metrics:
            results["scanned"] += 1

            # isolation forest
            anomalies = detect_anomalies(host, metric)
            results["anomalies"].extend([
                {
                    "host":           a.host,
                    "metric":         a.metric,
                    "value":          a.value,
                    "expected_range": a.expected_range,
                    "severity":       a.severity,
                    "score":          a.score,
                    "timestamp":      a.timestamp,
                }
                for a in anomalies
                if a.severity in ("high", "critical")
            ])

            # threshold breach
            breach = detect_threshold_breach(host, metric)
            if breach:
                results["breaches"].append(breach)

    return results