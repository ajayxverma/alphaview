import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from alphaview_discovery.evidence_models import ResearchOperation, ResearchState

COUNTERS = {"pages", "queries", "paid_calls", "requests"}


def budget_stop(budget: dict, usage: dict, cost: dict, deadline: datetime | None, cancelled: bool) -> str | None:
    if cancelled:
        return "cancelled"
    if deadline is not None and datetime.now(UTC) >= deadline:
        return "time_budget"
    for name, amount in cost.items():
        if name not in COUNTERS or not isinstance(amount, int) or amount < 0:
            raise ValueError("Invalid budget operation")
        if usage.get(name, 0) + amount > budget.get(name, 0):
            return f"{name}_budget"
    return None


async def locked_state(session, run_id: uuid.UUID, workspace_id: uuid.UUID) -> ResearchState:
    state = await session.scalar(select(ResearchState).where(
        ResearchState.run_id == run_id, ResearchState.workspace_id == workspace_id
    ).with_for_update())
    if state is None:
        raise LookupError("Research not found")
    return state


async def reserve(session, run_id: uuid.UUID, workspace_id: uuid.UUID, key: str, kind: str, cost: dict) -> ResearchOperation | None:
    state = await locked_state(session, run_id, workspace_id)
    existing = await session.scalar(select(ResearchOperation).where(
        ResearchOperation.run_id == run_id, ResearchOperation.workspace_id == workspace_id, ResearchOperation.key == key
    ))
    if existing is not None:
        return existing
    reason = budget_stop(state.budget, state.usage, cost, state.deadline, state.cancel_requested)
    if reason:
        state.stop_reason = reason
        return None
    state.usage = {**state.usage, **{name: state.usage.get(name, 0) + amount for name, amount in cost.items()}}
    operation = ResearchOperation(id=uuid.uuid5(run_id, key), run_id=run_id, workspace_id=workspace_id,
                                  key=key, kind=kind, cost=cost, status="reserved")
    session.add(operation)
    await session.flush()
    return operation