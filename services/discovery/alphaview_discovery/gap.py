import math

KeywordMetrics = dict[str, dict[str, float]]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def aggregate_external(keywords: list[str], kw_metrics: KeywordMetrics) -> dict[str, float]:
    rows = [kw_metrics[k] for k in keywords if k in kw_metrics]
    if not rows:
        return {}

    def vals(name: str) -> list[float]:
        return [r[name] for r in rows if name in r]

    out: dict[str, float] = {}
    for name in ("search_volume", "cpc", "serp_results"):
        if v := vals(name):
            out[name] = max(v)
    for name in ("competition", "trend_growth"):
        if v := vals(name):
            out[name] = round(sum(v) / len(v), 4)
    for name in ("owned_impressions", "owned_clicks", "owned_site_searches"):
        if v := vals(name):
            out[name] = sum(v)
    return out


def score_gap(cluster: dict, kw_metrics: KeywordMetrics, connectors_used: list[str]) -> dict:
    """GapScore = (D_volume * D_velocity * I_intensity) / (S_density * S_quality), squashed to 0-100."""
    ext = aggregate_external(cluster["keywords"], kw_metrics)

    d_volume = math.log10(
        1 + cluster["size"] * 10 + cluster["engagement"] / 10 + ext.get("search_volume", 0) + ext.get("owned_impressions", 0) / 10
    )
    d_velocity = _clamp(cluster["velocity"] * (1 + _clamp(ext.get("trend_growth", 0), -0.9, 3)), 0.25, 6)
    intensity = 0.1 + 0.35 * cluster["neg_sentiment"] + 0.45 * cluster["demand_ratio"] + 0.2 * cluster["unanswered_ratio"]

    s_density = (
        0.3
        + 1.5 * cluster["supply_ratio"]
        + ext.get("competition", 0)
        + math.log10(1 + ext.get("serp_results", 0)) / 10
    )
    # Heavy complaining about existing products implies incumbents are weak.
    s_quality = 1 - 0.5 * cluster["complaint_ratio"]
    supply = s_density * s_quality

    raw = d_volume * d_velocity * intensity / supply
    gap_score = round(100 * (1 - math.exp(-raw / 2.5)), 1)
    confidence = round(min(1.0, cluster["size"] / 60) * 0.6 + min(1.0, len(connectors_used) / 2) * 0.4, 2)

    return {
        "gap_score": gap_score,
        "confidence": confidence,
        "metrics": {
            "mentions": cluster["size"],
            "engagement": cluster["engagement"],
            "velocity": cluster["velocity"],
            "negative_sentiment": cluster["neg_sentiment"],
            "demand_intent_ratio": cluster["demand_ratio"],
            "complaint_ratio": cluster["complaint_ratio"],
            "supply_ratio": cluster["supply_ratio"],
            "unanswered_ratio": cluster["unanswered_ratio"],
            "sources": cluster["sources"],
            "components": {
                "demand_volume": round(d_volume, 3),
                "demand_velocity": round(d_velocity, 3),
                "pain_intensity": round(intensity, 3),
                "supply_density": round(s_density, 3),
                "supply_quality": round(s_quality, 3),
            },
            "external": ext,
            "connectors_used": connectors_used,
        },
    }
