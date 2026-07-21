"""
Tests for PromptExecutor: dequeues prompts, calls the model via Frangels,
optionally cross-reviews, and persists results.

All collaborators (store, orchestrator, event bus, event store) are injected
and mocked. No infra.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services import prompt_executor as pe
from app.services.prompt_executor import PromptExecutor


@pytest.fixture
def store():
    return AsyncMock()


@pytest.fixture
def orch():
    return AsyncMock()


def _ok(content="out", **extra):
    base = {
        "success": True, "content": content, "model": "m", "provider": "p",
        "tokens_input": 1, "tokens_output": 2, "cost_usd": 0.0,
    }
    base.update(extra)
    return base


# --------------------------------------------------------------------------
# _reset_daily_counters (pure)
# --------------------------------------------------------------------------

def test_reset_daily_counters_resets_on_new_day(store):
    ex = PromptExecutor(store)
    ex.completed_today = 9
    ex.failed_today = 4
    ex._today_date = None  # forces "new day"
    ex._reset_daily_counters()
    assert ex.completed_today == 0
    assert ex.failed_today == 0
    assert ex._today_date is not None


def test_reset_daily_counters_noop_same_day(store):
    ex = PromptExecutor(store)
    ex._reset_daily_counters()  # sets today
    ex.completed_today = 3
    ex._reset_daily_counters()  # same day -> no reset
    assert ex.completed_today == 3


# --------------------------------------------------------------------------
# _call_model
# --------------------------------------------------------------------------

async def test_call_model_no_orchestrator(store):
    ex = PromptExecutor(store)  # no orchestrator
    result = await ex._call_model({"content": "hi"})
    assert result["success"] is False
    assert "orchestrator" in result["error"]


async def test_call_model_work_auto_upgrades_paid(store, orch):
    orch.chat.return_value = _ok()
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    await ex._call_model({"content": "hi", "category": "work"})
    assert orch.chat.await_args.kwargs["prefer_paid"] is True


async def test_call_model_exception_returns_failure(store, orch):
    orch.chat.side_effect = RuntimeError("down")
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    result = await ex._call_model({"content": "hi", "category": "note"})
    assert result["success"] is False
    assert "down" in result["error"]


# --------------------------------------------------------------------------
# _review_output
# --------------------------------------------------------------------------

async def test_review_output_no_orchestrator(store):
    ex = PromptExecutor(store)
    assert await ex._review_output("p", "o") is None


async def test_review_output_parses_and_clamps(store, orch):
    orch.chat.return_value = {"success": True, "content": "1.7"}
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    assert await ex._review_output("p", "o") == 1.0  # clamped to 1.0


async def test_review_output_invalid_number_returns_none(store, orch):
    orch.chat.return_value = {"success": True, "content": "great!"}
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    assert await ex._review_output("p", "o") is None


async def test_review_output_exception_returns_none(store, orch):
    orch.chat.side_effect = RuntimeError("x")
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    assert await ex._review_output("p", "o") is None


# --------------------------------------------------------------------------
# _execute_prompt
# --------------------------------------------------------------------------

async def test_execute_prompt_happy_path_completes(store, orch):
    orch.chat.return_value = _ok(content="answer")
    bus = AsyncMock()
    estore = AsyncMock()
    ex = PromptExecutor(store, frangels_orchestrator=orch, event_bus=bus, event_store=estore)

    await ex._execute_prompt({"prompt_id": "p1", "category": "note", "content": "hi"})

    # last update marks completed with the output
    final = store.update_prompt.await_args
    assert final.kwargs["status"] == "completed"
    assert final.kwargs["output"] == "answer"
    assert ex.completed_today == 1
    assert ex.active_count == 0  # released in finally
    bus.publish.assert_awaited_once()
    estore.append_event.assert_awaited_once()


async def test_execute_prompt_runs_review_for_work(store, orch, monkeypatch):
    monkeypatch.setattr(pe.settings, "prompt_review_enabled", True, raising=False)
    orch.chat.side_effect = [_ok(content="answer"), {"success": True, "content": "0.9"}]
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "work", "content": "hi"})

    assert store.update_prompt.await_args.kwargs["review_score"] == 0.9
    assert orch.chat.await_count == 2  # execute + review


async def test_execute_prompt_model_failure_marks_failed(store, orch):
    orch.chat.return_value = {"success": False, "error": "no quota"}
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "note", "content": "hi"})

    assert store.update_prompt.await_args.kwargs["status"] == "failed"
    assert ex.failed_today == 1
    assert ex.completed_today == 0


async def test_execute_prompt_exception_marks_failed(store, orch):
    # First update (processing) raises; handler's update (failed) succeeds.
    store.update_prompt.side_effect = [RuntimeError("db"), None]
    orch.chat.return_value = _ok()
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "note", "content": "hi"})

    assert ex.failed_today == 1
    assert ex.active_count == 0
    assert store.update_prompt.await_args.kwargs["status"] == "failed"


async def test_execute_prompt_event_errors_swallowed(store, orch):
    orch.chat.return_value = _ok()
    bus = AsyncMock()
    bus.publish.side_effect = RuntimeError("bus")
    estore = AsyncMock()
    estore.append_event.side_effect = RuntimeError("store")
    ex = PromptExecutor(store, frangels_orchestrator=orch, event_bus=bus, event_store=estore)

    await ex._execute_prompt({"prompt_id": "p1", "category": "note", "content": "hi"})
    assert ex.completed_today == 1  # completed despite event failures


# --------------------------------------------------------------------------
# _execute_prompt — huecos que el mutation-testing destapó (C109). Cada test MATA
# una mutación que sobrevivía a la suite previa (100% líneas ≠ comportamiento pineado).
# --------------------------------------------------------------------------


async def test_execute_prompt_reviews_plan_category(store, orch, monkeypatch):
    """El review corre para `plan`, no solo `work`. Mata la mutación que reduce las
    categorías revisadas a `("work",)` (que sobrevivía: ningún test revisaba un `plan`)."""
    monkeypatch.setattr(pe.settings, "prompt_review_enabled", True, raising=False)
    orch.chat.side_effect = [_ok(content="answer"), {"success": True, "content": "0.8"}]
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "plan", "content": "hi"})

    assert store.update_prompt.await_args.kwargs["review_score"] == 0.8
    assert orch.chat.await_count == 2  # execute + review también para `plan`


async def test_execute_prompt_review_uses_free_tier(store, orch, monkeypatch):
    """La 2ª llamada (el review) usa `prefer_paid=False` — free tier. Mata la mutación que
    lo pone en True (sobrevivía: ningún test miraba el prefer_paid del review)."""
    monkeypatch.setattr(pe.settings, "prompt_review_enabled", True, raising=False)
    orch.chat.side_effect = [_ok(content="answer"), {"success": True, "content": "0.9"}]
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "work", "content": "hi"})

    review_call = orch.chat.await_args_list[1]  # la segunda llamada es el review
    assert review_call.kwargs["prefer_paid"] is False, (
        "el review debe usar free tier (prefer_paid=False), no gastar paid"
    )


async def test_execute_prompt_completed_increments_iterations(store, orch):
    """Al completar, `iterations` es el previo + 1. Mata la mutación del `+ 1` (sobrevivía:
    ningún test asertaba el valor de iterations)."""
    orch.chat.return_value = _ok()
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt(
        {"prompt_id": "p1", "category": "note", "content": "hi", "iterations": 2}
    )

    final = store.update_prompt.await_args
    assert final.kwargs["status"] == "completed"
    assert final.kwargs["iterations"] == 3  # 2 previas + 1


async def test_execute_prompt_publishes_to_idm_prompts_channel(store, orch):
    """El evento de completado se publica en el canal `idm.prompts` con el shape esperado.
    Mata la mutación del nombre del canal (sobrevivía: el test solo contaba la llamada)."""
    orch.chat.return_value = _ok(content="answer")
    bus = AsyncMock()
    ex = PromptExecutor(store, frangels_orchestrator=orch, event_bus=bus)

    await ex._execute_prompt({"prompt_id": "p1", "category": "note", "content": "hi"})

    channel, payload = bus.publish.await_args.args
    assert channel == "idm.prompts", f"canal inesperado: {channel}"
    assert payload["type"] == "prompt.completed"
    assert payload["prompt_id"] == "p1"


async def test_execute_prompt_model_failure_reports_the_model_error(store, orch):
    """Un resultado fallido toma la rama de fallo INTENCIONADA (early-return con el error del
    modelo), no la del `except` por un KeyError accidental. Mata la mutación que desactiva el
    guard `if not result["success"]` (sobrevivía porque el `except` producía el mismo
    status='failed' — pero con el error equivocado). Se asertan las señales que SÓLO da la
    rama intencionada: el error del modelo y que NO se intentó review ni completado."""
    orch.chat.return_value = {"success": False, "error": "no quota"}
    ex = PromptExecutor(store, frangels_orchestrator=orch)

    await ex._execute_prompt({"prompt_id": "p1", "category": "work", "content": "hi"})

    final = store.update_prompt.await_args
    assert final.kwargs["status"] == "failed"
    assert final.kwargs["error"] == "no quota", (
        "debe reportar el error del MODELO (rama intencionada), no un KeyError del except"
    )
    assert orch.chat.await_count == 1, "no debe intentar review tras un fallo de modelo"


# --------------------------------------------------------------------------
# lifecycle + loop
# --------------------------------------------------------------------------

async def test_start_stop(store):
    store.get_queued_prompts.return_value = []
    ex = PromptExecutor(store)
    await ex.start()
    assert ex.running is True
    first = ex._task
    await ex.start()  # no-op
    assert ex._task is first
    await ex.stop()
    assert ex._task.done()


async def test_run_loop_processes_then_cancels(store, orch, monkeypatch):
    orch.chat.return_value = _ok()
    store.get_queued_prompts.return_value = [
        {"prompt_id": "p1", "category": "note", "content": "hi"},
    ]
    ex = PromptExecutor(store, frangels_orchestrator=orch)
    ex.running = True

    async def fake_sleep(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(pe.asyncio, "sleep", fake_sleep)
    await ex._run_loop()
    store.get_queued_prompts.assert_awaited()
    assert ex.completed_today == 1


async def test_run_loop_error_branch(store, monkeypatch):
    store.get_queued_prompts.side_effect = RuntimeError("boom")
    ex = PromptExecutor(store)
    ex.running = True

    sleeps = {"n": 0}

    async def fake_sleep(_):
        sleeps["n"] += 1
        ex.running = False  # exit after error-branch sleep

    monkeypatch.setattr(pe.asyncio, "sleep", fake_sleep)
    await ex._run_loop()
    assert sleeps["n"] == 1
