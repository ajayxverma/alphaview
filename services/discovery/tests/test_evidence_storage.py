import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alphaview_common.research import ResearchBudget, ResearchOptions
from alphaview_discovery.budgets import reserve
from alphaview_discovery.deep_api import initialize_deep
from alphaview_discovery.evidence import DocumentInput, search_passages, store_attempts, store_document
from alphaview_discovery.evidence_models import (
    ResearchAttempt,
    ResearchDocument,
    ResearchOperation,
    ResearchPassage,
    ResearchState,
    ResearchVersion,
)
from alphaview_discovery.migrate import migration_config, upgrade_database
from alphaview_discovery.models import DiscoveryRun


@pytest.fixture
async def database():
    url = os.environ.get("ALPHAVIEW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ALPHAVIEW_TEST_DATABASE_URL to a disposable PostgreSQL database")
    if not (make_url(url).database or "").startswith("alphaview_test_"):
        raise ValueError("Integration tests require an alphaview_test_ database; refusing other databases")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA IF EXISTS discovery CASCADE"))
    await upgrade_database(engine)
    yield engine
    await engine.dispose()


def new_run():
    return DiscoveryRun(id=uuid.uuid4(), workspace_id=uuid.uuid4(), query="invoice", sources=["github"],
                        status="completed", signal_count=1)


async def test_repeat_upgrade_preserves_quick_run(database):
    run = new_run()
    async with AsyncSession(database, expire_on_commit=False) as session:
        session.add(run)
        await session.commit()
    await upgrade_database(database)
    async with AsyncSession(database) as session:
        assert await session.get(DiscoveryRun, run.id)
        assert await session.scalar(text("SELECT version_num FROM discovery.alembic_version")) == "0003_deep_operations"


async def test_existing_baseline_adoption_preserves_data(database):
    run = new_run()
    async with AsyncSession(database, expire_on_commit=False) as session:
        session.add(run)
        await session.commit()
    async with database.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(migration_config(sync), "0001_quick_baseline"))
        await connection.execute(text("DROP TABLE discovery.alembic_version"))
    await upgrade_database(database)
    async with AsyncSession(database) as session:
        assert await session.get(DiscoveryRun, run.id)


async def test_idempotent_evidence_lexical_retrieval_and_workspace_isolation(database):
    run = new_run()
    async with AsyncSession(database, expire_on_commit=False) as session:
        session.add(run)
        await session.commit()
        document = DocumentInput(requested_url="https://example.com/pricing", final_url="https://example.com/pricing",
            title="Invoice pricing", source="web", document_type="pricing", published_at=None,
            text="Background information. " * 250 + "Invoice automation costs $19 per month.")
        first = await store_document(session, run.id, run.workspace_id, document)
        assert await store_document(session, run.id, run.workspace_id, document) == first
        attempt = {"source": "reddit", "query": "invoice", "outcome": "blocked", "detail": "HTTP 403"}
        await store_attempts(session, run.id, run.workspace_id, [attempt, attempt])
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(ResearchDocument)) == 1
        assert await session.scalar(select(func.count()).select_from(ResearchAttempt)) == 1
        results = await search_passages(session, run.id, run.workspace_id, "invoice", document_type="pricing")
        assert results and any("$19" in item["text"] for item in results)
        assert results[0]["date_uncertainty"] == "unknown" and results[0]["published_at"] is None
        assert await search_passages(session, run.id, run.workspace_id, "invoice", date_from=datetime(2026, 1, 1, tzinfo=UTC)) == []
        with pytest.raises(LookupError):
            await search_passages(session, run.id, uuid.uuid4(), "invoice")
        assert await session.scalar(select(func.count()).select_from(ResearchPassage)) > 1


def test_document_dates_are_never_invented_and_canonical_is_local():
    document = DocumentInput(requested_url="https://example.com/pricing", final_url="https://example.com/pricing",
                            title="Pricing", source="web", document_type="pricing", text="Monthly plan costs $19")
    assert document.published_at is None
    with pytest.raises(ValueError):
        DocumentInput(**{**document.model_dump(), "canonical_url": "https://unrelated.example/pricing"})


async def setup_deep(database):
    run = new_run()
    options = ResearchOptions(mode="deep", seed_urls=["https://example.com/pricing"],
        budget=ResearchBudget(seconds=60, pages=1, queries=1, paid_calls=0, rounds=1, requests=2))
    async with AsyncSession(database, expire_on_commit=False) as session:
        session.add(run)
        await session.flush()
        await initialize_deep(session, run, options)
        await session.commit()
    return run


async def test_atomic_concurrent_budget_reservations_and_duplicate_keys(database):
    run = await setup_deep(database)

    async def attempt(key):
        async with AsyncSession(database, expire_on_commit=False) as session:
            operation = await reserve(session, run.id, run.workspace_id, key, "read", {"pages": 1})
            await session.commit()
            return operation.id if operation else None

    results = await asyncio.gather(attempt("a"), attempt("b"))
    assert sum(result is not None for result in results) == 1
    accepted = "a" if results[0] else "b"
    assert await attempt(accepted) == next(result for result in results if result)
    async with AsyncSession(database) as session:
        state = await session.get(ResearchState, run.id)
        assert state.usage["pages"] == 1
        state.cancel_requested = True
        await session.commit()
    assert await attempt("cancelled") is None


async def test_checkpointed_reads_claims_and_report_versions(database, monkeypatch):
    from alphaview_discovery import deep
    run = await setup_deep(database)
    monkeypatch.setattr(deep, "SessionLocal", async_sessionmaker(database, expire_on_commit=False))
    action = await deep.deep_next(str(run.id), "same-decision")
    assert await deep.deep_next(str(run.id), "same-decision") == action
    assert action["kind"] == "read"
    async with AsyncSession(database, expire_on_commit=False) as session:
        document_id = await store_document(session, run.id, run.workspace_id, DocumentInput(
            requested_url=action["url"], final_url=action["url"], title="Invoice pricing", source="web", document_type="pricing",
            text="Invoice pricing costs nineteen dollars per month for the standard plan. " * 4))
        await session.commit()
    await deep.deep_record(str(run.id), action["id"], {"outcome": "fetched", "document_id": str(document_id)})
    stop = await deep.deep_next(str(run.id))
    assert stop["kind"] == "stop"
    assert await deep.deep_finish(str(run.id), stop["reason"]) == 1
    assert await deep.deep_finish(str(run.id), stop["reason"]) == 1
    async with AsyncSession(database, expire_on_commit=False) as session:
        version = await session.scalar(select(ResearchVersion).where(ResearchVersion.run_id == run.id))
        assert version.report["claims"] and all(claim["status"] == "supported" for claim in version.report["claims"])
        state = await session.get(ResearchState, run.id)
        state.cancel_requested = True
        state.epoch += 1
        await session.commit()
    assert (await deep.deep_next(str(run.id)))["reason"] == "cancelled"
    assert (await deep.deep_next(str(run.id), "old-worker", 1))["reason"] == "superseded"
    assert await deep.deep_finish(str(run.id), "workflow_interrupted", 1) == 0
    assert await deep.deep_finish(str(run.id), "cancelled") == 2
    async with AsyncSession(database) as session:
        assert await session.scalar(select(func.count()).select_from(ResearchVersion)) == 2
        assert await session.scalar(select(func.count()).select_from(ResearchDocument)) == 1
        assert await session.scalar(select(func.count()).select_from(ResearchOperation).where(ResearchOperation.kind == "read")) == 1


async def test_request_permits_are_one_use_and_continuation_preserves_usage(database, monkeypatch):
    from types import SimpleNamespace

    import httpx

    from alphaview_common.auth import Principal, get_principal
    from alphaview_discovery import deep, deep_api
    from alphaview_discovery.main import app
    from alphaview_discovery.models import get_db

    run = await setup_deep(database)
    async with AsyncSession(database, expire_on_commit=False) as session:
        operation = await reserve(session, run.id, run.workspace_id, "read-test", "read", {"pages": 1})
        operation.result = {"url": "https://example.com/pricing"}
        operation_id = operation.id
        await session.commit()
    factory = async_sessionmaker(database, expire_on_commit=False)

    async def db_override():
        async with factory() as session:
            yield session

    async def fake_start(*args, **kwargs):
        assert kwargs["id"].endswith("-2")

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_principal] = lambda: Principal(uuid.uuid4(), run.workspace_id)
    monkeypatch.setattr(deep_api, "decode_token", lambda *args, **kwargs: {"operation": str(operation_id), "run": str(run.id), "ws": str(run.workspace_id)})
    monkeypatch.setattr(deep, "SessionLocal", factory)
    monkeypatch.setattr(app.state, "temporal", SimpleNamespace(start_workflow=fake_start), raising=False)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.post("/research/internal/request", json={"index": 1, "url": "https://example.com/robots.txt"})).json()["allowed"]
            assert not (await client.post("/research/internal/request", json={"index": 1, "url": "https://example.com/robots.txt"})).json()["allowed"]
            assert (await client.post(f"/discovery/{run.id}/cancel")).status_code == 202
            assert not (await client.post("/research/internal/request", json={"index": 2, "url": "https://example.com/pricing"})).json()["allowed"]
            await deep.deep_finish(str(run.id), "cancelled")
            response = await client.post(f"/discovery/{run.id}/continue", json={"additional_budget": {
                "seconds": 60, "pages": 1, "queries": 1, "paid_calls": 0, "rounds": 1, "requests": 2}})
            assert response.status_code == 202, response.text
            assert response.json()["epoch"] == 2
        async with factory() as session:
            state = await session.get(ResearchState, run.id)
            assert state.usage["requests"] == 1 and state.budget["requests"] == 4
            assert await session.scalar(select(func.count()).select_from(ResearchVersion)) == 1
    finally:
        app.dependency_overrides.clear()