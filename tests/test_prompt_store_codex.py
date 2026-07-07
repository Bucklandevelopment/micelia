"""
Tests for PromptStore service.
Generated with pytest-asyncio, mocked SQLAlchemy async session.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.models.prompt import PromptListModel, PromptModel
from app.services.prompt_store import PromptStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prompt_model(**overrides):
    """Create a PromptModel-like object with sensible defaults."""
    defaults = dict(
        prompt_id=uuid4(),
        content="Test prompt content",
        category="note",
        priority=5,
        status="pending",
        model_used=None,
        provider_used=None,
        prefer_paid=False,
        review_score=None,
        iterations=0,
        output=None,
        error=None,
        created_at=datetime.now(timezone.utc),
        scheduled_at=None,
        processing_at=None,
        completed_at=None,
        parent_prompt_id=None,
        correlation_id=None,
        tags=["test"],
        metadata_json={},
        source="api",
        tokens_input=0,
        tokens_output=0,
        latency_ms=None,
        cost_usd=None,
        workflow="quick_execute",
        classified_at=None,
        staged_at=None,
        archived_at=None,
        promoted_to=None,
        promoted_ref=None,
        provider_policy="free-first",
    )
    defaults.update(overrides)
    obj = MagicMock(spec=PromptModel)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _make_list_model(**overrides):
    defaults = dict(
        list_id=uuid4(),
        name="Test List",
        slug="test-list",
        description="A test list",
        category="general",
        content_md="",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        metadata_json={},
    )
    defaults.update(overrides)
    obj = MagicMock(spec=PromptListModel)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_session_ctx(session_mock):
    """Return an async context manager that yields the mock session."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store():
    """PromptStore with mocked async_session factory."""
    s = PromptStore()
    s.engine = MagicMock()
    # We'll override async_session per test via _mock_session_ctx
    return s


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# create_prompt
# ---------------------------------------------------------------------------

class TestCreatePrompt:

    @pytest.mark.asyncio
    async def test_create_prompt_returns_uuid(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.create_prompt(content="Hello world")
        assert isinstance(result, UUID)
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_prompt_with_all_fields(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))
        pid = uuid4()
        cid = uuid4()

        result = await store.create_prompt(
            content="Deep work",
            category="work",
            priority=8,
            tags=["dev", "focus"],
            scheduled_at=datetime.now(timezone.utc),
            parent_prompt_id=pid,
            correlation_id=cid,
            source="calendar",
            prefer_paid=True,
            metadata={"key": "val"},
            status="queued",
            workflow="reviewed_execute",
            provider_policy="paid-for-work",
        )
        assert isinstance(result, UUID)

        added_obj = mock_session.add.call_args[0][0]
        assert added_obj.content == "Deep work"
        assert added_obj.category == "work"
        assert added_obj.priority == 8
        assert added_obj.tags == ["dev", "focus"]
        assert added_obj.prefer_paid is True
        assert added_obj.status == "queued"
        assert added_obj.workflow == "reviewed_execute"
        assert added_obj.provider_policy == "paid-for-work"

    @pytest.mark.asyncio
    async def test_create_prompt_defaults(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_prompt(content="minimal")
        added = mock_session.add.call_args[0][0]
        assert added.category == "note"
        assert added.priority == 5
        assert added.status == "pending"
        assert added.tags == []
        assert added.source == "api"
        assert added.prefer_paid is False
        assert added.workflow == "quick_execute"
        assert added.provider_policy == "free-first"


# ---------------------------------------------------------------------------
# get_prompt
# ---------------------------------------------------------------------------

class TestGetPrompt:

    @pytest.mark.asyncio
    async def test_get_prompt_found(self, store, mock_session):
        pid = uuid4()
        prompt_obj = _make_prompt_model(prompt_id=pid, content="Found it")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = prompt_obj
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.get_prompt(pid)
        assert result is not None
        assert result["prompt_id"] == str(pid)
        assert result["content"] == "Found it"

    @pytest.mark.asyncio
    async def test_get_prompt_not_found(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.get_prompt(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# update_prompt
# ---------------------------------------------------------------------------

class TestUpdatePrompt:

    @pytest.mark.asyncio
    async def test_update_prompt_success(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.update_prompt(uuid4(), status="completed")
        assert ok is True
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_prompt_not_found(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 0
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.update_prompt(uuid4(), status="completed")
        assert ok is False


# ---------------------------------------------------------------------------
# delete_prompt
# ---------------------------------------------------------------------------

class TestDeletePrompt:

    @pytest.mark.asyncio
    async def test_delete_prompt_success(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.delete_prompt(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_delete_prompt_not_found(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 0
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.delete_prompt(uuid4())
        assert ok is False


# ---------------------------------------------------------------------------
# create_note (hashtag detection + category mapping)
# ---------------------------------------------------------------------------

class TestCreateNote:

    @pytest.mark.asyncio
    async def test_create_note_basic(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        pid = await store.create_note("Buy groceries")
        assert isinstance(pid, UUID)
        added = mock_session.add.call_args[0][0]
        assert added.content == "Buy groceries"
        assert added.category == "note"
        assert added.source == "note"
        assert added.status == "captured"

    @pytest.mark.asyncio
    async def test_create_note_hashtag_extraction(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Deploy service #work #deploy")
        added = mock_session.add.call_args[0][0]
        assert "work" in added.tags
        assert "deploy" in added.tags
        # Text should be cleaned of hashtags
        assert "#work" not in added.content
        assert "#deploy" not in added.content

    @pytest.mark.asyncio
    async def test_create_note_category_auto_mapping_work(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Fix CI pipeline #work")
        added = mock_session.add.call_args[0][0]
        assert added.category == "work"

    @pytest.mark.asyncio
    async def test_create_note_category_auto_mapping_plan(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Q3 roadmap #plan")
        added = mock_session.add.call_args[0][0]
        assert added.category == "plan"

    @pytest.mark.asyncio
    async def test_create_note_category_auto_mapping_project(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("New feature #project")
        added = mock_session.add.call_args[0][0]
        assert added.category == "project"

    @pytest.mark.asyncio
    async def test_create_note_category_auto_mapping_routine(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Morning standup #routine")
        added = mock_session.add.call_args[0][0]
        assert added.category == "routine"

    @pytest.mark.asyncio
    async def test_create_note_category_auto_mapping_personal(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Dentist appointment #personal")
        added = mock_session.add.call_args[0][0]
        assert added.category == "personal"

    @pytest.mark.asyncio
    async def test_create_note_category_spanish_tags(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Revisar informe #trabajo")
        added = mock_session.add.call_args[0][0]
        assert added.category == "work"

    @pytest.mark.asyncio
    async def test_create_note_urgent_priority(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Server is down #urgent")
        added = mock_session.add.call_args[0][0]
        assert added.priority == 10

    @pytest.mark.asyncio
    async def test_create_note_low_priority(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Nice to have #low")
        added = mock_session.add.call_args[0][0]
        assert added.priority == 2

    @pytest.mark.asyncio
    async def test_create_note_merges_explicit_and_auto_tags(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Task #work", tags=["sprint-1"])
        added = mock_session.add.call_args[0][0]
        assert "work" in added.tags
        assert "sprint-1" in added.tags

    @pytest.mark.asyncio
    async def test_create_note_deduplicates_tags(self, store, mock_session):
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.create_note("Do thing #work", tags=["work"])
        added = mock_session.add.call_args[0][0]
        assert added.tags.count("work") == 1


# ---------------------------------------------------------------------------
# list_prompts
# ---------------------------------------------------------------------------

class TestListPrompts:

    @pytest.mark.asyncio
    async def test_list_prompts_no_filter(self, store, mock_session):
        p1 = _make_prompt_model(content="A")
        p2 = _make_prompt_model(content="B")

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [p1, p2]

        count_result = MagicMock()
        count_result.scalar.return_value = 2

        query_result = MagicMock()
        query_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, query_result])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.list_prompts()
        assert result["total"] == 2
        assert result["count"] == 2
        assert len(result["prompts"]) == 2
        assert result["limit"] == 50
        assert result["offset"] == 0

    @pytest.mark.asyncio
    async def test_list_prompts_filter_status(self, store, mock_session):
        p1 = _make_prompt_model(status="pending")

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [p1]
        count_result = MagicMock()
        count_result.scalar.return_value = 1
        query_result = MagicMock()
        query_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, query_result])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.list_prompts(status="pending")
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_list_prompts_filter_category(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        query_result = MagicMock()
        query_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, query_result])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.list_prompts(category="work")
        assert result["total"] == 0
        assert result["prompts"] == []

    @pytest.mark.asyncio
    async def test_list_prompts_pagination(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        count_result = MagicMock()
        count_result.scalar.return_value = 100
        query_result = MagicMock()
        query_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, query_result])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.list_prompts(limit=10, offset=20)
        assert result["limit"] == 10
        assert result["offset"] == 20
        assert result["total"] == 100

    @pytest.mark.asyncio
    async def test_list_prompts_filter_source(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        query_result = MagicMock()
        query_result.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(side_effect=[count_result, query_result])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        result = await store.list_prompts(source="calendar")
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# get_pending_prompts / get_queued_prompts
# ---------------------------------------------------------------------------

class TestPendingAndQueued:

    @pytest.mark.asyncio
    async def test_get_pending_prompts(self, store, mock_session):
        p1 = _make_prompt_model(status="pending")
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [p1]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        results = await store.get_pending_prompts()
        assert len(results) == 1
        assert results[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_pending_prompts_empty(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        results = await store.get_pending_prompts()
        assert results == []

    @pytest.mark.asyncio
    async def test_get_pending_prompts_with_limit(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        await store.get_pending_prompts(limit=5)
        # Verify execute was called (query construction validated)
        mock_session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_queued_prompts(self, store, mock_session):
        p1 = _make_prompt_model(status="queued", priority=8)
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [p1]
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        results = await store.get_queued_prompts()
        assert len(results) == 1
        assert results[0]["status"] == "queued"

    @pytest.mark.asyncio
    async def test_get_queued_prompts_empty(self, store, mock_session):
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock

        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        results = await store.get_queued_prompts()
        assert results == []


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:

    @pytest.mark.asyncio
    async def test_get_stats(self, store, mock_session):
        # Total count
        total_result = MagicMock()
        total_result.scalar.return_value = 42

        # By status
        status_result = MagicMock()
        status_result.all.return_value = [("pending", 10), ("completed", 30), ("failed", 2)]

        # By category
        cat_result = MagicMock()
        cat_result.all.return_value = [("work", 20), ("note", 15), ("plan", 7)]

        # Completed today
        completed_result = MagicMock()
        completed_result.scalar.return_value = 5

        # Tokens
        tokens_row = (1500, 3000, 0.25)
        tokens_result = MagicMock()
        tokens_result.one.return_value = tokens_row

        # Latency
        latency_result = MagicMock()
        latency_result.scalar.return_value = 123.45

        mock_session.execute = AsyncMock(side_effect=[
            total_result,
            status_result,
            cat_result,
            completed_result,
            tokens_result,
            latency_result,
        ])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        stats = await store.get_stats()
        assert stats["total"] == 42
        assert stats["by_status"] == {"pending": 10, "completed": 30, "failed": 2}
        assert stats["by_category"] == {"work": 20, "note": 15, "plan": 7}
        assert stats["completed_today"] == 5
        assert stats["total_tokens_input"] == 1500
        assert stats["total_tokens_output"] == 3000
        assert stats["total_cost_usd"] == 0.25
        assert stats["avg_latency_ms"] == 123.45

    @pytest.mark.asyncio
    async def test_get_stats_empty_db(self, store, mock_session):
        total_result = MagicMock()
        total_result.scalar.return_value = 0

        status_result = MagicMock()
        status_result.all.return_value = []

        cat_result = MagicMock()
        cat_result.all.return_value = []

        completed_result = MagicMock()
        completed_result.scalar.return_value = 0

        tokens_result = MagicMock()
        tokens_result.one.return_value = (0, 0, 0)

        latency_result = MagicMock()
        latency_result.scalar.return_value = None  # triggers fallback to 0

        mock_session.execute = AsyncMock(side_effect=[
            total_result,
            status_result,
            cat_result,
            completed_result,
            tokens_result,
            latency_result,
        ])
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        stats = await store.get_stats()
        assert stats["total"] == 0
        assert stats["by_status"] == {}
        assert stats["avg_latency_ms"] == 0


# ---------------------------------------------------------------------------
# classify_prompt / stage_prompt / archive_prompt
# ---------------------------------------------------------------------------

class TestLifecycleMethods:

    @pytest.mark.asyncio
    async def test_classify_prompt(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.classify_prompt(uuid4(), "work", tags=["dev"])
        assert ok is True

    @pytest.mark.asyncio
    async def test_stage_prompt(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.stage_prompt(uuid4())
        assert ok is True

    @pytest.mark.asyncio
    async def test_archive_prompt(self, store, mock_session):
        result_mock = MagicMock()
        result_mock.rowcount = 1
        mock_session.execute = AsyncMock(return_value=result_mock)
        store.async_session = MagicMock(return_value=_mock_session_ctx(mock_session))

        ok = await store.archive_prompt(uuid4())
        assert ok is True


# ---------------------------------------------------------------------------
# _prompt_to_dict serialization
# ---------------------------------------------------------------------------

class TestSerialization:

    def test_prompt_to_dict(self, store):
        pid = uuid4()
        now = datetime.now(timezone.utc)
        prompt = _make_prompt_model(
            prompt_id=pid,
            content="Serialize me",
            category="work",
            priority=7,
            status="completed",
            created_at=now,
            tags=["a", "b"],
            tokens_input=100,
            tokens_output=200,
        )

        result = store._prompt_to_dict(prompt)
        assert result["prompt_id"] == str(pid)
        assert result["content"] == "Serialize me"
        assert result["category"] == "work"
        assert result["priority"] == 7
        assert result["tags"] == ["a", "b"]
        assert result["tokens_input"] == 100
        assert result["tokens_output"] == 200
        assert result["created_at"] == now.isoformat()

    def test_prompt_to_dict_none_dates(self, store):
        prompt = _make_prompt_model(
            scheduled_at=None,
            processing_at=None,
            completed_at=None,
            classified_at=None,
            staged_at=None,
            archived_at=None,
        )
        result = store._prompt_to_dict(prompt)
        assert result["scheduled_at"] is None
        assert result["completed_at"] is None
