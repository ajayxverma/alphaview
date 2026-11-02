from datetime import UTC, datetime, timedelta

from alphaview_common.signals import Signal
from alphaview_nlp.pipeline import annotate, classify_intent, cluster_signals


def _sig(i: int, text: str, days_ago: int = 1) -> Signal:
    return Signal(
        source="hackernews",
        external_id=str(i),
        url=f"https://example.com/{i}",
        title=text,
        text="",
        created_at=datetime.now(UTC) - timedelta(days=days_ago),
        engagement=i,
    )


def test_classify_intent():
    assert classify_intent("Is there a tool that reconciles invoices?") == "wish"
    assert classify_intent("Looking for an alternative to QuickBooks") == "wish"
    assert classify_intent("Switched from Xero, it was too expensive") == "alternative"
    assert classify_intent("Their sync is broken and I hate it") == "complaint"
    assert classify_intent("Show HN: I built an invoice tool") == "solution"
    assert classify_intent("Interesting article") == "discussion"


def test_cluster_output_contract():
    texts = (
        ["is there a tool for invoice reconciliation in small accounting firms"] * 15
        + ["podcast editing software is too expensive and clunky for audio creators"] * 15
        + ["show hn: i built a podcast editing app for audio creators"] * 3
    )
    signals = [_sig(i, t + f" #{i}", days_ago=i % 60) for i, t in enumerate(texts)]
    annotate(signals)
    clusters = cluster_signals(signals, "small business")
    assert clusters
    assert sum(c["size"] for c in clusters) <= len(signals)
    # Fields consumed by discovery's gap engine and the strategist.
    required = {
        "label", "keywords", "size", "engagement", "velocity", "neg_sentiment", "demand_ratio",
        "complaint_ratio", "supply_ratio", "unanswered_ratio", "sources", "evidence", "excerpts",
    }
    for c in clusters:
        assert required <= c.keys()


def test_small_corpus_single_cluster():
    signals = [_sig(i, f"need a tool for x {i}") for i in range(5)]
    annotate(signals)
    clusters = cluster_signals(signals, "x")
    assert len(clusters) == 1 and clusters[0]["size"] == 5


def test_evidence_includes_each_contributing_source_with_provenance():
    signals = [_sig(index, "invoice problem") for index in range(9)]
    signals[0].source = "mastodon"
    signals[0].text = "Public post excerpt"
    signals[1].source = "github"
    cluster = cluster_signals(signals, "invoice")[0]
    assert cluster["sources"] == {"mastodon": 1, "github": 1, "hackernews": 7}
    assert {item["source"] for item in cluster["evidence"]} == set(cluster["sources"])
    social = next(item for item in cluster["evidence"] if item["source"] == "mastodon")
    assert social["excerpt"] == "Public post excerpt"
    assert social["published_at"] and social["url"]


def test_web_editorial_evidence_has_lower_demand_weight():
    community = _sig(1, "Invoice software is broken")
    web = _sig(2, "Invoice software is broken")
    web.source = "web"
    annotate([community, web])
    direct = cluster_signals([community], "invoice")[0]
    editorial = cluster_signals([web], "invoice")[0]
    assert editorial["demand_ratio"] == direct["demand_ratio"] / 2
    assert editorial["complaint_ratio"] == direct["complaint_ratio"] / 2
