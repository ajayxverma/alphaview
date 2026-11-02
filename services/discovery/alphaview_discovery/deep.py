import hashlib
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import urlsplit

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from temporalio import activity

from alphaview_common import contracts
from alphaview_common.research import QUESTIONS, ResearchOptions
from alphaview_discovery.budgets import budget_stop, locked_state, reserve
from alphaview_discovery.evidence import search_passages
from alphaview_discovery.evidence_models import (
    ResearchAttempt,
    ResearchCandidate,
    ResearchClaim,
    ResearchDocument,
    ResearchOperation,
    ResearchPassage,
    ResearchVersion,
)
from alphaview_discovery.models import DiscoveryRun, SessionLocal
from alphaview_discovery.research import lexical_score, plan_questions, terms

HINTS = {
    "problems": {"problem", "workflow", "challenge", "difficult", "frustrated", "manual"},
    "solutions": {"product", "solution", "documentation", "features", "software"},
    "buying": {"pricing", "price", "cost", "plans", "subscription", "switching"},
    "experience": {"customer", "review", "experience", "users", "used"},
    "context": {"statistics", "report", "survey", "study", "market"},
    "counter": {"successful", "satisfied", "success", "improved", "works", "recommend"},
}


def relevant_to_question(topic: str, question: str, text: str) -> bool:
    return lexical_score(topic, text) >= 0.25 and bool(terms(text) & HINTS[question])


def permitted_domain(url: str, options: ResearchOptions) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return not any(host == domain.lower() or host.endswith("." + domain.lower()) for domain in options.excluded_domains)


def independent_domain(domain: str) -> str:
    return ".".join(domain.lower().split(".")[-2:])


def contextual_claim_status(claim: dict, passage: dict, document: dict, topic: str, question: str) -> str:
    quote = claim.get("quotation", "")
    offset = passage.get("offset", 0)
    if claim.get("passage_id") != str(passage["id"]) or claim.get("document_id") != str(document["id"]):
        return "unverified"
    if document["text"][offset:offset + len(passage["text"])] != passage["text"] or not quote or quote not in passage["text"]:
        return "unverified"
    if not relevant_to_question(topic, question, quote) or len(quote.split()) < 8:
        return "partial"
    if claim.get("kind") == "observation" and claim["text"] == f'According to {document["title"]}: "{quote}"':
        return "supported"
    return "partial"


async def assess(session, run, state):
    documents = list(await session.scalars(select(ResearchDocument).where(
        ResearchDocument.run_id == run.id, ResearchDocument.workspace_id == run.workspace_id)))
    topic = state.usage.get("topic", run.query)
    coverage = {question: {"domains": sorted({independent_domain(document.domain) for document in documents
                if relevant_to_question(topic, question, document.text)}), "adequate": False} for question in QUESTIONS}
    for value in coverage.values():
        value["adequate"] = len(value["domains"]) >= 2
    state.coverage = coverage
    state.unresolved = [question for question, value in coverage.items() if not value["adequate"]]
    return documents


@activity.defn(name=contracts.DEEP_NEXT)
async def deep_next(run_id: str, decision_id: str | None = None, expected_epoch: int | None = None) -> dict:
    async with SessionLocal() as session:
        run = await session.get(DiscoveryRun, uuid.UUID(run_id))
        state = await locked_state(session, run.id, run.workspace_id)
        if expected_epoch is not None and state.epoch != expected_epoch:
            return {"kind": "stop", "reason": "superseded"}
        decision_key = f"decision:{decision_id}" if decision_id else None
        if decision_key:
            previous = await session.scalar(select(ResearchOperation).where(ResearchOperation.run_id == run.id,
                ResearchOperation.workspace_id == run.workspace_id, ResearchOperation.key == decision_key))
            if previous is not None:
                return previous.result

        async def checkpoint(action):
            state.updated_at = datetime.now(UTC)
            if decision_key:
                session.add(ResearchOperation(id=uuid.uuid5(run.id, decision_key), run_id=run.id, workspace_id=run.workspace_id,
                    key=decision_key, kind="decision", cost={}, status="completed", result=action))
            await session.commit()
            return action

        options = ResearchOptions.model_validate(run.research_config)
        reason = budget_stop(state.budget, state.usage, {}, state.deadline, state.cancel_requested) or state.stop_reason
        if reason:
            return await checkpoint({"kind": "stop", "reason": reason})
        documents = await assess(session, run, state)
        if not state.unresolved:
            return await checkpoint({"kind": "stop", "reason": "coverage_adequate"})
        operations = list(await session.scalars(select(ResearchOperation).where(
            ResearchOperation.run_id == run.id, ResearchOperation.workspace_id == run.workspace_id)))
        seeds = options.seed_urls
        for url in seeds:
            key = hashlib.sha256(f"seed:{url}".encode()).hexdigest()
            await session.execute(insert(ResearchCandidate).values(id=uuid.uuid5(run.id, key), run_id=run.id, workspace_id=run.workspace_id,
                key=key, url=url, question_id="problems", query=run.query, provider="seed", title="User seed", priority=1)
                .on_conflict_do_nothing(constraint="uq_candidate_key"))
        if state.round == 0:
            state.round = 1
        topic = state.usage.get("topic", run.query)
        plans = plan_questions(topic, run.geo)
        round_searches = [operation for operation in operations if operation.kind == "search" and operation.result.get("round") == state.round
                  and operation.result.get("epoch") == state.epoch]
        searched = {operation.result.get("question_id") for operation in round_searches}
        can_search = "web" in run.sources and state.usage.get("queries", 0) < state.budget["queries"] and state.usage.get("paid_calls", 0) < state.budget["paid_calls"]
        if can_search and len(round_searches) < 6:
            ordered = sorted(plans, key=lambda plan: (len(state.coverage[plan["id"]]["domains"]), list(QUESTIONS).index(plan["id"])))
            for plan in ordered:
                if plan["id"] in searched or plan["id"] not in state.unresolved:
                    continue
                if state.round > 1:
                    plan["query"] += ["", "", " independent case study", " limitations comparison", " primary source evidence", " independent reviews"][min(state.round, 5)]
                key = "search:" + hashlib.sha256(plan["query"].encode()).hexdigest()
                if any(operation.key == key for operation in operations):
                    continue
                operation = await reserve(session, run.id, run.workspace_id, key, "search", {"queries": 1, "paid_calls": 1})
                if operation is None:
                    return await checkpoint({"kind": "stop", "reason": state.stop_reason})
                operation.result = {"round": state.round, "epoch": state.epoch, "question_id": plan["id"], "query": plan["query"]}
                state.phase = "search"
                return await checkpoint({"kind": "search", "id": str(operation.id), "workspace_id": str(run.workspace_id),
                    "question": plan, "options": options.model_dump(mode="json"), "geo": run.geo})
        frontier = list(await session.scalars(select(ResearchCandidate).where(
            ResearchCandidate.run_id == run.id, ResearchCandidate.workspace_id == run.workspace_id, ResearchCandidate.outcome == "pending")))
        def priority(candidate):
            domain = independent_domain(urlsplit(candidate.url).hostname or "")
            novelty = domain not in state.coverage[candidate.question_id]["domains"]
            preferred = any((urlsplit(candidate.url).hostname or "").endswith(host) for host in options.preferred_domains)
            return (len(state.coverage[candidate.question_id]["domains"]) < 2, novelty,
                    lexical_score(topic, candidate.title + " " + candidate.snippet), preferred, -(candidate.position or 99))
        for candidate in sorted(frontier, key=priority, reverse=True):
            host = urlsplit(candidate.url).hostname or ""
            used = [operation for operation in operations if operation.kind == "read" and operation.result.get("url") == candidate.url]
            domain_reads = sum(operation.kind == "read" and urlsplit(operation.result.get("url", "")).hostname == host for operation in operations)
            domain_limit = 4 if re.search(r"pricing|docs|plans|documentation", candidate.url) else 2
            if not permitted_domain(candidate.url, options):
                candidate.outcome = "excluded"
                continue
            if used or domain_reads >= domain_limit:
                candidate.outcome = "duplicate" if used else "domain_limited"
                continue
            operation = await reserve(session, run.id, run.workspace_id, f"read:{candidate.key}", "read", {"pages": 1})
            if operation is None:
                return await checkpoint({"kind": "stop", "reason": state.stop_reason})
            candidate.outcome = "reading"
            operation.result = {"url": candidate.url, "candidate_id": str(candidate.id), "question_id": candidate.question_id, "epoch": state.epoch}
            state.phase = "read"
            return await checkpoint({"kind": "read", "id": str(operation.id), "workspace_id": str(run.workspace_id),
                                    "url": candidate.url, "options": options.model_dump(mode="json")})
        useful_count = sum(lexical_score(topic, document.text) >= 0.25 for document in documents)
        last_count = state.usage.get("previous_document_count", 0)
        gain = useful_count - last_count
        state.usage = {**state.usage, "previous_document_count": useful_count,
                       "low_gain_rounds": state.usage.get("low_gain_rounds", 0) + 1 if gain == 0 else 0}
        if state.round >= state.budget["rounds"]:
            reason = "round_budget"
        elif state.usage["low_gain_rounds"] >= 2:
            reason = "diminishing_returns"
        elif not can_search:
            reason = "frontier_exhausted"
        else:
            state.round += 1
            state.phase = "assess"
            return await checkpoint({"kind": "checkpoint"})
        return await checkpoint({"kind": "stop", "reason": reason})


@activity.defn(name=contracts.DEEP_RECORD)
async def deep_record(run_id: str, operation_id: str, result: dict) -> None:
    async with SessionLocal() as session:
        run = await session.get(DiscoveryRun, uuid.UUID(run_id))
        state = await locked_state(session, run.id, run.workspace_id)
        operation = await session.scalar(select(ResearchOperation).where(ResearchOperation.id == uuid.UUID(operation_id),
            ResearchOperation.run_id == run.id, ResearchOperation.workspace_id == run.workspace_id))
        if operation.status == "completed":
            return
        original = operation.result
        operation.result = {**original, **result}
        operation.status = "completed"
        if operation.kind == "search" and original.get("epoch") == state.epoch and result.get("outcome") in ("unsupported", "blocked", "rate_limited"):
            state.stop_reason = "source_rate_limited" if result["outcome"] == "rate_limited" else "search_unavailable"
        if operation.kind == "search":
            for item in result.get("candidates", []):
                key = hashlib.sha256(f"{item['url']}|{item['question_id']}|{item['query']}".encode()).hexdigest()
                await session.execute(insert(ResearchCandidate).values(id=uuid.uuid5(run.id, key), run_id=run.id, workspace_id=run.workspace_id,
                    key=key, url=item["url"], question_id=item["question_id"], query=item["query"], provider=item["provider"],
                    position=item.get("position"), title=item["title"], snippet=item["snippet"], retrieved_at=datetime.fromisoformat(item["retrieved_at"]))
                    .on_conflict_do_nothing(constraint="uq_candidate_key"))
        elif original.get("candidate_id"):
            candidate = await session.get(ResearchCandidate, uuid.UUID(original["candidate_id"]))
            candidate.outcome = result.get("outcome", "failed")
        key = str(operation.id)
        await session.execute(insert(ResearchAttempt).values(id=uuid.uuid5(run.id, key), run_id=run.id, workspace_id=run.workspace_id,
            key=hashlib.sha256(key.encode()).hexdigest(), source="web_search" if operation.kind == "search" else "web",
            query=original.get("query", run.query), question_id=original.get("question_id"), requested_url=original.get("url"),
            outcome=result.get("outcome", "failed"), detail=result.get("detail", "")[:500], signal_count=int(bool(result.get("document_id"))))
            .on_conflict_do_nothing(constraint="uq_attempt_key"))
        await session.commit()


@activity.defn(name=contracts.DEEP_FINISH)
async def deep_finish(run_id: str, reason: str, expected_epoch: int | None = None) -> int:
    async with SessionLocal() as session:
        run = await session.get(DiscoveryRun, uuid.UUID(run_id))
        state = await locked_state(session, run.id, run.workspace_id)
        if expected_epoch is not None and state.epoch != expected_epoch:
            return 0
        version_id = uuid.uuid5(run.id, f"deep-version:{state.epoch}")
        existing = await session.get(ResearchVersion, version_id)
        if existing:
            return existing.version
        documents = await assess(session, run, state)
        topic = state.usage.get("topic", run.query)
        retrieved = await search_passages(session, run.id, run.workspace_id, topic, match_all=False)
        document_map = {str(document.id): document for document in documents}
        claims = []
        for question in QUESTIONS:
            used_domains = set()
            for passage in retrieved:
                document = document_map[str(passage["document_id"])]
                domain = independent_domain(document.domain)
                if domain in used_domains or not relevant_to_question(topic, question, passage["text"]):
                    continue
                quote = next((sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", passage["text"])
                              if len(sentence) <= 500 and relevant_to_question(topic, question, sentence)), "")
                if not quote:
                    continue
                stored_passage = await session.get(ResearchPassage, passage["id"])
                claim = {"id": str(uuid.uuid5(version_id, f"{question}:{passage['id']}:{quote}")), "question_id": question,
                    "text": f'According to {document.title}: "{quote}"', "kind": "observation", "quotation": quote,
                    "document_id": str(document.id), "passage_id": str(passage["id"]), "url": document.final_url,
                    "source_type": document.document_type, "verification_method": "context_checked_source_attribution"}
                claim["status"] = contextual_claim_status(claim, {"id": passage["id"], "text": passage["text"], "offset": stored_passage.offset},
                    {"id": document.id, "title": document.title, "text": document.text}, topic, question)
                claims.append(claim)
                used_domains.add(domain)
                if len(used_domains) == 2:
                    break
        potential_conflicts = []
        buying = [claim for claim in claims if claim["question_id"] == "buying"]
        for first in buying:
            for second in buying:
                if first["id"] >= second["id"]:
                    continue
                first_prices = set(re.findall(r"[$€£]\s*\d+(?:\.\d+)?", first["quotation"]))
                second_prices = set(re.findall(r"[$€£]\s*\d+(?:\.\d+)?", second["quotation"]))
                if first_prices and second_prices and first_prices != second_prices:
                    potential_conflicts.append({"description": "Pricing quotations differ; check product, plan, dates and currency before drawing a comparison.", "claim_ids": [first["id"], second["id"]]})
        counter_ids = [claim["id"] for claim in claims if claim["question_id"] == "counter"]
        for claim in claims:
            session.add(ResearchClaim(id=uuid.UUID(claim["id"]), run_id=run.id, workspace_id=run.workspace_id,
                text=claim["text"], kind=claim["kind"], quotation=claim["quotation"], document_id=uuid.UUID(claim["document_id"]),
                passage_id=uuid.UUID(claim["passage_id"]), status=claim["status"],
                contradictions=[{"claim_id": value, "relationship": "counter_evidence_not_automatically_contradictory"} for value in counter_ids] if claim["question_id"] == "problems" else []))
        version = (await session.scalar(select(func.max(ResearchVersion.version)).where(ResearchVersion.run_id == run.id))) or 0
        supported_domains = {question: {independent_domain(urlsplit(claim["url"]).hostname or "") for claim in claims
            if claim["question_id"] == question and claim["status"] == "supported"} for question in QUESTIONS}
        state.unresolved = [question for question in QUESTIONS if len(supported_domains[question]) < 2]
        state.coverage = {question: {**state.coverage[question], "supported_claim_domains": sorted(supported_domains[question])}
                          for question in QUESTIONS}
        complete = reason == "coverage_adequate" and not state.unresolved and not potential_conflicts
        report = {"mode": "deep", "planner": "deterministic", "retrieval": "lexical_only", "synthesis": "evidence_attributions",
            "claims": claims, "potential_conflicts": potential_conflicts, "coverage": state.coverage, "unresolved": state.unresolved, "stop_reason": reason, "complete": complete,
            "usage": state.usage, "budget": state.budget,
            "interpretations": [{"kind": "interpretation", "text": "Source coverage identifies questions with independent corroboration, not market-wide demand."}],
            "hypotheses": [{"kind": "hypothesis", "text": "Startup feasibility and willingness to pay require direct customer validation."}],
            "limitations": ["Supported means a contextual source attribution; it does not establish that every source claim is true.",
                "Lexical-only retrieval; no semantic reranker or LLM-generated factual claims.",
                "Geography is approximate. Missing publication dates remain unknown. Promotional/reference pages are not customer demand.",
                "Automated contradiction resolution is unavailable; counter-evidence is searched and retained."]}
        session.add(ResearchVersion(id=version_id, run_id=run.id, workspace_id=run.workspace_id, version=version + 1, report=report))
        state.stop_reason, state.complete = reason, complete
        state.phase = "cancelled" if reason == "cancelled" else "completed"
        run.status = "cancelled" if reason == "cancelled" else "completed"
        run.finished_at = datetime.now(UTC)
        state.updated_at = run.finished_at
        await session.commit()
        return version + 1


DEEP_ACTIVITIES = [deep_next, deep_record, deep_finish]