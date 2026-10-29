import re

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from alphaview_common.signals import Signal

_analyzer = SentimentIntensityAnalyzer()

# Ordered by precedence: the first matching intent wins.
INTENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "wish",
        re.compile(
            r"\b(i wish|would (gladly |happily )?pay|is there (a|an|any) (tool|app|service|way|product|software)"
            r"|looking for (a|an|some)|does anyone know (of|a|any)|need (a|an) (tool|app|way|solution)"
            r"|why (is there no|isn't there)|someone should build)\b",
            re.I,
        ),
    ),
    (
        "alternative",
        re.compile(
            r"\b(alternatives? (to|for)|switch(ed|ing)? (from|away)|replacement for|instead of|cheaper than)\b",
            re.I,
        ),
    ),
    (
        "complaint",
        re.compile(
            r"\b(frustrat\w*|annoying|hate|terrible|awful|broken|sucks|waste of time|too expensive|overpriced"
            r"|clunky|outdated|nightmare|painful|so slow|doesn't work|does not work)\b",
            re.I,
        ),
    ),
    (
        "solution",
        re.compile(r"\b(i built|i made|we built|we launched|show hn|check out|i use|we use|try using)\b", re.I),
    ),
]
DEMAND_INTENTS = {"wish", "alternative", "complaint"}


def classify_intent(text: str) -> str:
    for name, pattern in INTENT_PATTERNS:
        if pattern.search(text):
            return name
    return "discussion"


def annotate(signals: list[Signal]) -> None:
    for s in signals:
        content = s.content[:2000]
        s.sentiment = float(_analyzer.polarity_scores(content)["compound"])
        s.intent = classify_intent(content)


def _summarize(members: list[Signal], label_terms: list[str], midpoint: float) -> dict:
    n = len(members)
    intents = [m.intent for m in members]
    se = [m for m in members if m.answered is not None]
    recent = sum(1 for m in members if m.created_at.timestamp() >= midpoint)
    top = sorted(members, key=lambda m: m.engagement + m.comments, reverse=True)
    sources: dict[str, int] = {}
    for m in members:
        sources[m.source] = sources.get(m.source, 0) + 1
    return {
        "label": ", ".join(label_terms[:3]),
        "keywords": label_terms[:5],
        "size": n,
        "engagement": int(sum(m.engagement + m.comments for m in members)),
        "velocity": round((recent + 1) / (n - recent + 1), 3),
        "neg_sentiment": round(float(np.mean([max(0.0, -m.sentiment) for m in members])), 3),
        "demand_ratio": round(sum(i in DEMAND_INTENTS for i in intents) / n, 3),
        "complaint_ratio": round(intents.count("complaint") / n, 3),
        "supply_ratio": round(intents.count("solution") / n, 3),
        "unanswered_ratio": round(sum(1 for m in se if not m.answered) / len(se), 3) if se else 0.0,
        "sources": sources,
        "evidence": [
            {
                "title": m.title[:200],
                "url": m.url,
                "source": m.source,
                "intent": m.intent,
                "sentiment": round(m.sentiment, 2),
                "engagement": m.engagement,
            }
            for m in top[:6]
        ],
        "excerpts": [m.content[:300] for m in top[:12]],
    }


def cluster_signals(signals: list[Signal], query: str) -> list[dict]:
    """Group signals into pain-point clusters with TF-IDF + KMeans and compute per-cluster demand stats."""
    if not signals:
        return []
    stamps = [s.created_at.timestamp() for s in signals]
    midpoint = (min(stamps) + max(stamps)) / 2
    query_terms = set(query.lower().split())

    if len(signals) < 12:
        return [_summarize(signals, [query], midpoint)]

    vectorizer = TfidfVectorizer(
        stop_words="english", max_features=5000, ngram_range=(1, 2), min_df=2, max_df=0.6, sublinear_tf=True
    )
    try:
        matrix = vectorizer.fit_transform([s.content for s in signals])
    except ValueError:  # empty vocabulary after pruning
        return [_summarize(signals, [query], midpoint)]

    k = max(2, min(8, len(signals) // 25))
    model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(matrix)
    terms = vectorizer.get_feature_names_out()

    clusters: list[dict] = []
    for idx in range(k):
        members = [s for s, lbl in zip(signals, model.labels_, strict=True) if lbl == idx]
        if len(members) < 3:
            continue
        order = np.argsort(model.cluster_centers_[idx])[::-1]
        label_terms = [terms[i] for i in order if terms[i] not in query_terms][:5]
        clusters.append(_summarize(members, label_terms or [query], midpoint))
    return clusters
