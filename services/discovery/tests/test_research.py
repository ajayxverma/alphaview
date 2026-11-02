import pytest
from pydantic import ValidationError

from alphaview_common.research import ResearchOptions
from alphaview_discovery.research import (
    near_duplicate,
    passages,
    plan_questions,
    rank_documents,
    verify_attributed_claim,
)


def test_old_clients_default_to_quick_and_date_ranges_are_validated():
    assert ResearchOptions().mode == "quick"
    with pytest.raises(ValidationError):
        ResearchOptions(date_from="2026-10-31", date_to="2026-10-01")


def test_plan_covers_counter_evidence_and_buying_not_only_complaints():
    assert {question["id"] for question in plan_questions("accounting")} == {
        "problems", "solutions", "buying", "experience", "context", "counter",
    }


def test_reference_passages_preserve_relevant_material_after_4000_characters():
    text = "Background information. " * 250 + "Invoice automation costs $19 per month."
    assert any("$19" in passage["text"] for passage in passages(text))
    assert passages(text) == passages(text)


def test_different_pricing_is_not_merged_as_near_duplicate():
    background = "A workflow product includes documentation and invoice automation tools. " * 40
    assert not near_duplicate(background + "Price $19", background + "Price $99")
    assert near_duplicate(background, background)


def test_matching_quote_alone_does_not_verify_a_market_claim():
    passage = {"id": "p1", "text": "We reduced invoice processing costs."}
    document = {"title": "Vendor case study"}
    claim = {"passage_id": "p1", "quotation": passage["text"], "text": "The entire market wants this product.", "kind": "hypothesis"}
    assert verify_attributed_claim(claim, passage, document) == "partial"
    claim.update(text=f'According to Vendor case study: "{passage["text"]}"', kind="observation")
    assert verify_attributed_claim(claim, passage, document) == "supported"
    claim["passage_id"] = "invented"
    assert verify_attributed_claim(claim, passage, document) == "unverified"


@pytest.mark.parametrize("topic", ["startup accounting", "invoice reconciliation", "pet insurance", "podcast editing",
                                   "Austin coworking", "rare disease caregiving", "evergreen pricing", "contradictory reviews"])
def test_provisional_fixture_benchmark(topic):
    relevant = [{"url": f"https://source{index}.example/report", "title": topic,
                 "text": f"Primary evidence about {topic}, pricing and counter-evidence.", "relevant": True,
                 "engagement": index} for index in range(10)]
    unrelated = [{"url": f"https://noise{index}.example/post", "title": "Unrelated popular entertainment",
                 "text": "Celebrity news and sports", "relevant": False, "engagement": 100 + index} for index in range(10)]
    baseline = sorted(relevant + unrelated, key=lambda document: document["engagement"], reverse=True)[:10]
    ranked = rank_documents(topic, relevant + unrelated)[:10]
    assert sum(document["relevant"] for document in baseline) / 10 == 0
    assert sum(document["relevant"] for document in ranked) / 10 == 1