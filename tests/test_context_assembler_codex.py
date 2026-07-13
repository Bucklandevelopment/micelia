"""
Tests for ContextAssembler: builds the final prompt from 5 context layers.

Boundaries are all injectable/patchable: prompt_store & skills_manager are
mocked, filesystem layers use tmp_path + monkeypatched settings/cwd, and the
temporal layer patches the module datetime. No infra.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import context_assembler as ca
from app.services.context_assembler import ContextAssembler, ContextLayer, get_context_assembler

# --------------------------------------------------------------------------
# ContextLayer + assemble()
# --------------------------------------------------------------------------

def test_context_layer_repr():
    layer = ContextLayer(2, "Temporal", "hello")
    assert "Temporal" in repr(layer)
    assert "2" in repr(layer)


async def test_assemble_returns_raw_content_when_all_layers_empty():
    asm = ContextAssembler()
    # Only include layer 4 with no correlation/tags -> empty -> raw content.
    out = await asm.assemble({"content": "hola"}, include_layers=[4])
    assert out == "hola"


async def test_assemble_includes_selected_layers():
    asm = ContextAssembler()
    out = await asm.assemble({"content": "do X", "tags": ["urgent"]}, include_layers=[2, 4])
    assert "## Task" in out
    assert "do X" in out
    assert "[Temporal]" in out
    assert "Tags: urgent" in out


async def test_assemble_all_layers_default(tmp_path, monkeypatch):
    # Default = all 5 layers; exercises every _layer_N append inside assemble().
    monkeypatch.setattr(ca.os, "getcwd", lambda: str(tmp_path))
    monkeypatch.setattr(ca.settings, "prompt_lists_dir", str(tmp_path), raising=False)
    asm = ContextAssembler()
    out = await asm.assemble({"content": "hello", "category": "note", "tags": []})
    assert "## Task" in out
    assert "hello" in out
    assert "[Identity]" in out  # layer 0 always emits settings identity


# --------------------------------------------------------------------------
# Layer 0: identity (cowork.md + cache)
# --------------------------------------------------------------------------

async def test_layer_0_reads_cowork_and_caches(tmp_path, monkeypatch):
    (tmp_path / "cowork.md").write_text("# Identidad\nSoy Jessicache\n")
    monkeypatch.setattr(ca.os, "getcwd", lambda: str(tmp_path))
    asm = ContextAssembler()

    layer = await asm._layer_0_identity()
    assert "cowork.md" in layer.content
    assert "Jessicache" in layer.content
    # Second call served from cache (even if cwd changes)
    monkeypatch.setattr(ca.os, "getcwd", lambda: "/nonexistent")
    cached = await asm._layer_0_identity()
    assert cached.content == asm._identity_cache


async def test_layer_0_without_cowork(tmp_path, monkeypatch):
    monkeypatch.setattr(ca.os, "getcwd", lambda: str(tmp_path))
    asm = ContextAssembler()
    layer = await asm._layer_0_identity()
    assert "System:" in layer.content  # still emits settings-based identity


async def test_layer_0_cowork_read_error_is_swallowed(tmp_path, monkeypatch):
    # cowork.md existe (os.path.exists True) pero no es legible: es un directorio,
    # así que open() lanza IsADirectoryError -> la rama `except Exception: pass`
    # (103-104) lo traga y sigue con la identidad base de settings.
    (tmp_path / "cowork.md").mkdir()
    monkeypatch.setattr(ca.os, "getcwd", lambda: str(tmp_path))
    asm = ContextAssembler()
    layer = await asm._layer_0_identity()
    assert "System:" in layer.content
    assert "cowork.md" not in layer.content


# --------------------------------------------------------------------------
# Layer 1: domain (prompt list md + frontmatter stripping)
# --------------------------------------------------------------------------

async def test_layer_1_domain_loads_list_and_strips_frontmatter(tmp_path, monkeypatch):
    monkeypatch.setattr(ca.settings, "prompt_lists_dir", str(tmp_path), raising=False)
    (tmp_path / "rutina-diaria.md").write_text(
        "---\ntitle: rutina\n---\nHacer ejercicio\n"
    )
    asm = ContextAssembler()
    layer = await asm._layer_1_domain({"category": "routine"})
    assert "rutina-diaria" in layer.content
    assert "Hacer ejercicio" in layer.content
    assert "title: rutina" not in layer.content  # frontmatter stripped


async def test_layer_1_domain_unknown_category_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ca.settings, "prompt_lists_dir", str(tmp_path), raising=False)
    asm = ContextAssembler()
    layer = await asm._layer_1_domain({"category": "note"})
    assert layer.content == ""


async def test_layer_1_domain_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ca.settings, "prompt_lists_dir", str(tmp_path), raising=False)
    asm = ContextAssembler()
    layer = await asm._layer_1_domain({"category": "work"})  # laboral.md absent
    assert layer.content == ""


async def test_layer_1_domain_read_error_is_swallowed(tmp_path, monkeypatch):
    # El md de la lista existe pero no es legible como archivo (es un directorio):
    # open() lanza IsADirectoryError -> `except Exception: pass` (144-145) lo traga
    # y la capa Domain se devuelve vacía sin propagar.
    monkeypatch.setattr(ca.settings, "prompt_lists_dir", str(tmp_path), raising=False)
    (tmp_path / "rutina-diaria.md").mkdir()
    asm = ContextAssembler()
    layer = await asm._layer_1_domain({"category": "routine"})
    assert layer.content == ""


# --------------------------------------------------------------------------
# Layer 2: temporal (period branches)
# --------------------------------------------------------------------------

class _FixedDatetime:
    """Minimal stand-in exposing .now(tz) for the temporal layer."""

    def __init__(self, dt):
        self._dt = dt

    def now(self, tz=None):
        return self._dt


@pytest.mark.parametrize(
    "hour,expected",
    [(8, "Morning"), (13, "Midday"), (16, "Afternoon"), (20, "Evening"), (3, "Night")],
)
def test_layer_2_temporal_periods(hour, expected, monkeypatch):
    fixed = datetime(2026, 1, 5, hour, 0, 0, tzinfo=timezone.utc)  # Monday
    monkeypatch.setattr(ca, "datetime", _FixedDatetime(fixed))
    asm = ContextAssembler()
    layer = asm._layer_2_temporal()
    assert f"Period: {expected}" in layer.content
    assert "Day: Monday" in layer.content


# --------------------------------------------------------------------------
# Layer 3: operative (skills + providers)
# --------------------------------------------------------------------------

async def test_layer_3_operative_with_skills_and_paid_providers(monkeypatch):
    skills = MagicMock()
    skills.list_skills.return_value = [
        {"name": "wifi-scan", "is_active": True},
        {"name": "old", "is_active": False},
    ]
    monkeypatch.setattr(ca.settings, "openai_api_key", "sk-x", raising=False)
    monkeypatch.setattr(ca.settings, "anthropic_api_key", "sk-y", raising=False)
    asm = ContextAssembler(skills_manager=skills)
    layer = await asm._layer_3_operative()
    assert "wifi-scan" in layer.content
    assert "OpenAI" in layer.content
    assert "Anthropic" in layer.content


async def test_layer_3_operative_skills_error_swallowed(monkeypatch):
    skills = MagicMock()
    skills.list_skills.side_effect = RuntimeError("skills db down")
    monkeypatch.setattr(ca.settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(ca.settings, "anthropic_api_key", "", raising=False)
    asm = ContextAssembler(skills_manager=skills)
    layer = await asm._layer_3_operative()  # exception swallowed
    assert "Default model:" in layer.content


async def test_layer_3_operative_without_skills_manager(monkeypatch):
    monkeypatch.setattr(ca.settings, "openai_api_key", "", raising=False)
    monkeypatch.setattr(ca.settings, "anthropic_api_key", "", raising=False)
    asm = ContextAssembler()
    layer = await asm._layer_3_operative()
    assert "Default model:" in layer.content


# --------------------------------------------------------------------------
# Layer 4: live (related prompts + tags)
# --------------------------------------------------------------------------

async def test_layer_4_live_related_prompts_and_tags():
    store = AsyncMock()
    store.list_prompts.return_value = {
        "prompts": [
            {"prompt_id": "other", "correlation_id": "c1", "status": "done",
             "content": "related one"},
            {"prompt_id": "self", "correlation_id": "c1", "status": "x", "content": "me"},
        ]
    }
    asm = ContextAssembler(prompt_store=store)
    layer = await asm._layer_4_live(
        {"prompt_id": "self", "correlation_id": "c1", "tags": ["a", "b"]}
    )
    assert "Related prompts:" in layer.content
    assert "related one" in layer.content
    assert "me" not in layer.content.split("Related prompts:")[1]  # self excluded
    assert "Tags: a, b" in layer.content


async def test_layer_4_live_store_error_is_swallowed():
    store = AsyncMock()
    store.list_prompts.side_effect = RuntimeError("db down")
    asm = ContextAssembler(prompt_store=store)
    layer = await asm._layer_4_live({"correlation_id": "c1", "tags": []})
    assert layer.content == ""  # error swallowed, no tags


async def test_layer_4_live_no_store_no_correlation():
    asm = ContextAssembler()
    layer = await asm._layer_4_live({"tags": ["solo"]})
    assert layer.content == "Tags: solo"


# --------------------------------------------------------------------------
# Singleton
# --------------------------------------------------------------------------

def test_get_context_assembler_is_singleton(monkeypatch):
    monkeypatch.setattr(ca, "_assembler", None)
    a = get_context_assembler()
    b = get_context_assembler()
    assert a is b
