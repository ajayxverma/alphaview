from datetime import UTC, datetime, timedelta

import pytest

from alphaview_discovery.budgets import budget_stop
from alphaview_discovery.deep import contextual_claim_status


def test_budgets_cancel_time_and_all_counters():
    budget = {"pages": 2, "queries": 2, "requests": 2, "paid_calls": 2}
    for counter in budget:
        assert budget_stop(budget, {counter: 2}, {counter: 1}, None, False) == f"{counter}_budget"
    assert budget_stop(budget, {}, {"pages": 1}, datetime.now(UTC) - timedelta(seconds=1), False) == "time_budget"
    assert budget_stop(budget, {}, {}, None, True) == "cancelled"
    with pytest.raises(ValueError):
        budget_stop(budget, {}, {"pages": -1}, None, False)


def test_claim_context_and_identity_are_checked_not_just_quote_matching():
    text = "Invoice pricing costs nineteen dollars per month for the standard plan."
    document = {"id": "d1", "title": "Vendor pricing", "text": text}
    passage = {"id": "p1", "text": text, "offset": 0}
    claim = {"document_id": "d1", "passage_id": "p1", "quotation": text, "kind": "observation",
             "text": f'According to Vendor pricing: "{text}"'}
    assert contextual_claim_status(claim, passage, document, "invoice", "buying") == "supported"
    assert contextual_claim_status({**claim, "text": "The market will grow 100%"}, passage, document, "invoice", "buying") == "partial"
    assert contextual_claim_status(claim, passage, document, "pet insurance", "buying") == "partial"
    assert contextual_claim_status({**claim, "passage_id": "invented"}, passage, document, "invoice", "buying") == "unverified"