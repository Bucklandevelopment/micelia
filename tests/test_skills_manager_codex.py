"""
Tests for SkillsManager: CRUD dinámico de skills + matching/aplicación.

La única frontera externa es la session factory de SQLAlchemy async (reutilizada
del PromptStore). Se sustituye por un context manager AsyncMock que produce una
session mockeada, así que todo corre determinista — sin Postgres ni red.

Patrón de mock de session tomado de tests/test_prompt_store_codex.py.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import app.services.skills_manager as sm_module
from app.models.prompt import SkillModel
from app.services.skills_manager import SkillsManager, get_skills_manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_skill(**overrides):
    """SkillModel-like mock con defaults sensatos."""
    from app.core.time import utcnow_naive

    defaults = dict(
        skill_id="11111111-1111-1111-1111-111111111111",
        name="Summarize",
        slug="summarize",
        description="Resume texto",
        trigger_pattern="resume|summar",
        prompt_template="Resume esto: {content}",
        is_active=True,
        usage_count=3,
        created_at=utcnow_naive(),
        updated_at=None,
        metadata_json={"k": "v"},
    )
    defaults.update(overrides)
    obj = MagicMock(spec=SkillModel)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


def _mock_session_ctx(session_mock):
    """Async context manager que produce la session mockeada."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_result(*, scalar=None, scalars_all=None, rowcount=None):
    """Result mock para session.execute()."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    scalars = MagicMock()
    scalars.all.return_value = scalars_all if scalars_all is not None else []
    result.scalars.return_value = scalars
    if rowcount is not None:
        result.rowcount = rowcount
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session():
    s = AsyncMock()
    s.add = MagicMock()
    s.commit = AsyncMock()
    s.execute = AsyncMock()
    return s


@pytest.fixture
def manager(session):
    """SkillsManager con un PromptStore falso cuya async_session está mockeada."""
    prompt_store = MagicMock()
    prompt_store.async_session = MagicMock(return_value=_mock_session_ctx(session))
    return SkillsManager(prompt_store)


# ---------------------------------------------------------------------------
# async_session property
# ---------------------------------------------------------------------------

def test_async_session_property_returns_factory(manager):
    assert manager.async_session is manager.prompt_store.async_session


def test_async_session_uninitialized_raises():
    prompt_store = MagicMock()
    prompt_store.async_session = None
    mgr = SkillsManager(prompt_store)
    with pytest.raises(RuntimeError, match="PromptStore not initialized"):
        _ = mgr.async_session


# ---------------------------------------------------------------------------
# create_skill
# ---------------------------------------------------------------------------

async def test_create_skill_persists_and_returns_dict(manager, session):
    result = await manager.create_skill(
        name="My Cool Skill!",
        description="does things",
        trigger_pattern="cool|thing",
        prompt_template="Do: {content}",
        metadata={"a": 1},
    )
    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    assert result["name"] == "My Cool Skill!"
    # slug se genera slugificando el nombre
    assert result["slug"] == "my-cool-skill"
    assert result["is_active"] is True
    assert result["usage_count"] == 0
    assert result["metadata"] == {"a": 1}


async def test_create_skill_default_metadata(manager):
    result = await manager.create_skill(
        name="No Meta", description="d", trigger_pattern="x", prompt_template="{content}"
    )
    assert result["metadata"] == {}


async def test_create_skill_invalid_regex_raises(manager, session):
    with pytest.raises(ValueError, match="Invalid trigger_pattern regex"):
        await manager.create_skill(
            name="Bad", description="d", trigger_pattern="[unclosed", prompt_template="{content}"
        )
    # No debe tocar la BD si la validación falla
    session.add.assert_not_called()


# ---------------------------------------------------------------------------
# get_skill / list_skills
# ---------------------------------------------------------------------------

async def test_get_skill_found(manager, session):
    skill = _make_skill(slug="summarize")
    session.execute.return_value = _make_result(scalar=skill)
    out = await manager.get_skill("summarize")
    assert out is not None
    assert out["slug"] == "summarize"
    assert out["usage_count"] == 3


async def test_get_skill_not_found(manager, session):
    session.execute.return_value = _make_result(scalar=None)
    assert await manager.get_skill("missing") is None


async def test_list_skills(manager, session):
    skills = [_make_skill(slug="a", name="A"), _make_skill(slug="b", name="B")]
    session.execute.return_value = _make_result(scalars_all=skills)
    out = await manager.list_skills()
    assert [s["slug"] for s in out] == ["a", "b"]


async def test_list_skills_empty(manager, session):
    session.execute.return_value = _make_result(scalars_all=[])
    assert await manager.list_skills() == []


# ---------------------------------------------------------------------------
# update_skill
# ---------------------------------------------------------------------------

async def test_update_skill_not_found_returns_none(manager, session):
    session.execute.return_value = _make_result(rowcount=0)
    out = await manager.update_skill("missing", {"description": "new"})
    assert out is None


async def test_update_skill_success_recomputes_slug(manager, session):
    updated = _make_skill(slug="new-name", name="New Name")
    # 1ª execute = UPDATE (rowcount=1); 2ª = SELECT dentro de get_skill
    session.execute.side_effect = [
        _make_result(rowcount=1),
        _make_result(scalar=updated),
    ]
    out = await manager.update_skill("old", {"name": "New Name"})
    assert out is not None
    assert out["slug"] == "new-name"


async def test_update_skill_invalid_regex_raises(manager):
    with pytest.raises(ValueError, match="Invalid trigger_pattern regex"):
        await manager.update_skill("s", {"trigger_pattern": "(unbalanced"})


# ---------------------------------------------------------------------------
# delete_skill
# ---------------------------------------------------------------------------

async def test_delete_skill_existing(manager, session):
    session.execute.return_value = _make_result(rowcount=1)
    assert await manager.delete_skill("summarize") is True
    session.commit.assert_awaited()


async def test_delete_skill_missing(manager, session):
    session.execute.return_value = _make_result(rowcount=0)
    assert await manager.delete_skill("missing") is False


# ---------------------------------------------------------------------------
# toggle_skill
# ---------------------------------------------------------------------------

async def test_toggle_skill_flips_state(manager, session):
    skill = _make_skill(is_active=True)
    # 1ª execute = SELECT (encuentra skill), 2ª = UPDATE
    session.execute.side_effect = [
        _make_result(scalar=skill),
        _make_result(rowcount=1),
    ]
    new_state = await manager.toggle_skill("summarize")
    assert new_state is False


async def test_toggle_skill_missing(manager, session):
    session.execute.return_value = _make_result(scalar=None)
    assert await manager.toggle_skill("missing") is None


# ---------------------------------------------------------------------------
# test_skill (aplica template)
# ---------------------------------------------------------------------------

async def test_test_skill_applies_template(manager, session):
    skill = _make_skill(prompt_template="Resume: {content}")
    session.execute.return_value = _make_result(scalar=skill)
    out = await manager.test_skill("summarize", "hola mundo")
    assert out == "Resume: hola mundo"


async def test_test_skill_missing(manager, session):
    session.execute.return_value = _make_result(scalar=None)
    assert await manager.test_skill("missing", "x") is None


# ---------------------------------------------------------------------------
# match_skill
# ---------------------------------------------------------------------------

async def test_match_skill_first_match_increments_usage(manager, session):
    match = _make_skill(slug="summarize", trigger_pattern="resume")
    # 1ª execute = SELECT skills activas; 2ª = UPDATE de _increment_usage
    session.execute.side_effect = [
        _make_result(scalars_all=[match]),
        _make_result(rowcount=1),
    ]
    out = await manager.match_skill("por favor resume este texto")
    assert out is not None
    assert out["slug"] == "summarize"
    # _increment_usage disparó un segundo execute + commit
    assert session.execute.await_count == 2


async def test_match_skill_no_match(manager, session):
    skill = _make_skill(trigger_pattern="zzz")
    session.execute.return_value = _make_result(scalars_all=[skill])
    assert await manager.match_skill("nada que ver") is None


async def test_match_skill_skips_empty_pattern(manager, session):
    skill = _make_skill(trigger_pattern="")
    session.execute.return_value = _make_result(scalars_all=[skill])
    assert await manager.match_skill("cualquier cosa") is None


async def test_match_skill_skips_invalid_regex(manager, session):
    bad = _make_skill(slug="bad", trigger_pattern="[bad")
    session.execute.return_value = _make_result(scalars_all=[bad])
    # regex inválida se traga con warning y continúa → sin match
    assert await manager.match_skill("texto") is None


# ---------------------------------------------------------------------------
# apply_skill (puro)
# ---------------------------------------------------------------------------

def test_apply_skill_replaces_content(manager):
    out = manager.apply_skill({"prompt_template": "X: {content} :Y"}, "hola")
    assert out == "X: hola :Y"


def test_apply_skill_default_template(manager):
    out = manager.apply_skill({}, "hola")
    assert out == "hola"


def test_apply_skill_missing_key_fallback(manager):
    # template con un placeholder desconocido → format lanza KeyError → fallback replace
    out = manager.apply_skill({"prompt_template": "{unknown} {content}"}, "hola")
    assert "hola" in out


# ---------------------------------------------------------------------------
# _increment_usage exception path
# ---------------------------------------------------------------------------

async def test_increment_usage_swallows_errors(manager, session):
    session.execute.side_effect = RuntimeError("db down")
    # No debe propagar
    await manager._increment_usage("summarize")


# ---------------------------------------------------------------------------
# _skill_to_dict
# ---------------------------------------------------------------------------

def test_skill_to_dict_with_updated_at(manager):
    from app.core.time import utcnow_naive

    ts = utcnow_naive()
    skill = _make_skill(updated_at=ts, usage_count=None)
    d = manager._skill_to_dict(skill)
    assert d["updated_at"] == ts.isoformat()
    assert d["usage_count"] == 0  # None → 0


# ---------------------------------------------------------------------------
# get_skills_manager singleton
# ---------------------------------------------------------------------------

def test_get_skills_manager_requires_store_first(monkeypatch):
    monkeypatch.setattr(sm_module, "_skills_manager", None)
    with pytest.raises(RuntimeError, match="requires prompt_store"):
        get_skills_manager()


def test_get_skills_manager_singleton(monkeypatch):
    monkeypatch.setattr(sm_module, "_skills_manager", None)
    store = MagicMock()
    first = get_skills_manager(store)
    second = get_skills_manager()  # ya inicializado, no requiere store
    assert first is second
