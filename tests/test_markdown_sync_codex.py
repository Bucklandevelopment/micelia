"""
Tests for MarkdownSyncService (app.services.markdown_sync).

Bidirectional DB<->Markdown sync. Two boundaries, both isolated here (no DB, no
network, no real clock):

  - **``PromptStore``** — the only injected collaborator. ``_store(**overrides)`` hands
    back a ``MagicMock`` whose 6 used methods (``list_all_lists``,
    ``get_captured_prompts``, ``get_archived_prompts``, ``get_list``, ``update_list``,
    ``create_list``) are ``AsyncMock`` with empty defaults; each test overrides what it
    needs.
  - **File I/O** — the service exposes ``lists_dir``/``inbox_dir``/``archive_dir`` as
    plain string attributes, so ``_svc`` redirects them into ``tmp_path``; the real
    ``open``/``os.makedirs`` run against pytest's sandbox and we assert on written files.
  - **Clock** — ``app.services.markdown_sync.utcnow_naive`` is monkeypatched to a fixed
    ``datetime`` so ``YYYY/MM/YYYY-MM-DD`` inbox paths and ``get_today_inbox_md`` are
    deterministic.

``asyncio_mode = auto`` (pyproject) → ``async def test_*`` needs no marker.

Covers: start/stop/_run_loop lifecycle, the 3 DB->MD syncs, the MD->DB sync, full_sync
(happy + per-branch error capture), the frontmatter parse/build helpers, _parse_bool,
_ensure_dirs, _read_file/_write_file, get_status, get_today_inbox_md.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import app.services.markdown_sync as ms
from app.services.markdown_sync import MarkdownSyncService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2026, 7, 11, 9, 30, 0)


def _store(**overrides):
    """A mock PromptStore with the 6 used methods as AsyncMock (empty defaults)."""
    store = MagicMock()
    store.list_all_lists = AsyncMock(return_value=overrides.get("list_all_lists", []))
    store.get_captured_prompts = AsyncMock(
        return_value=overrides.get("get_captured_prompts", [])
    )
    store.get_archived_prompts = AsyncMock(
        return_value=overrides.get("get_archived_prompts", {"prompts": []})
    )
    store.get_list = AsyncMock(return_value=overrides.get("get_list", None))
    store.update_list = AsyncMock(return_value=overrides.get("update_list", True))
    store.create_list = AsyncMock(return_value=overrides.get("create_list", "new-id"))
    return store


def _svc(tmp_path: Path, store=None) -> MarkdownSyncService:
    """Build a service with its 3 dirs redirected into ``tmp_path``."""
    svc = MarkdownSyncService(store or _store())
    svc.lists_dir = str(tmp_path / "prompt-lists")
    svc.inbox_dir = str(tmp_path / "prompt-inbox")
    svc.archive_dir = str(tmp_path / "prompt-archives")
    return svc


# ---------------------------------------------------------------------------
# Lifecycle: start / stop / _run_loop
# ---------------------------------------------------------------------------


async def test_start_creates_dirs_and_task(tmp_path):
    svc = _svc(tmp_path)
    await svc.start()
    try:
        assert svc.running is True
        assert svc._task is not None
        assert Path(svc.lists_dir).is_dir()
        assert Path(svc.inbox_dir).is_dir()
        assert Path(svc.archive_dir).is_dir()
    finally:
        await svc.stop()


async def test_start_noop_when_task_alive(tmp_path):
    svc = _svc(tmp_path)
    await svc.start()
    try:
        first = svc._task
        await svc.start()  # second call must not replace the live task
        assert svc._task is first
    finally:
        await svc.stop()


async def test_stop_cancels_and_swallows(tmp_path):
    svc = _svc(tmp_path)
    await svc.start()
    task = svc._task
    await svc.stop()
    assert svc.running is False
    assert task.cancelled() or task.done()


async def test_stop_without_task_noop(tmp_path):
    svc = _svc(tmp_path)
    # never started -> _task is None
    await svc.stop()
    assert svc.running is False


async def test_run_loop_happy_then_cancel(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    svc.running = True
    calls = {"sync": 0}

    async def _full_sync():
        calls["sync"] += 1
        return {}

    async def _sleep(_):
        # after one successful cycle, stop the loop so it exits cleanly next check
        svc.running = False

    monkeypatch.setattr(svc, "full_sync", _full_sync)
    monkeypatch.setattr(ms.asyncio, "sleep", _sleep)

    await svc._run_loop()
    assert calls["sync"] == 1


async def test_run_loop_cancelled_error_breaks(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    svc.running = True

    async def _full_sync():
        raise asyncio.CancelledError()

    monkeypatch.setattr(svc, "full_sync", _full_sync)
    # Should break out without re-raising
    await svc._run_loop()


async def test_run_loop_generic_exception_logged_then_sleep(tmp_path, monkeypatch):
    svc = _svc(tmp_path)
    svc.running = True

    async def _full_sync():
        raise RuntimeError("boom")

    async def _sleep(_):
        svc.running = False  # exit after the error branch's sleep

    monkeypatch.setattr(svc, "full_sync", _full_sync)
    monkeypatch.setattr(ms.asyncio, "sleep", _sleep)

    await svc._run_loop()  # must not raise


# ---------------------------------------------------------------------------
# DB -> MD: sync_lists_to_md
# ---------------------------------------------------------------------------


async def test_sync_lists_to_md_writes_new(tmp_path):
    store = _store(
        list_all_lists=[
            {
                "slug": "daily",
                "name": "Daily",
                "category": "work",
                "description": "d",
                "is_active": True,
                "content_md": "body here",
            }
        ]
    )
    svc = _svc(tmp_path, store)
    Path(svc.lists_dir).mkdir(parents=True)

    written = await svc.sync_lists_to_md()
    assert written == 1

    out = Path(svc.lists_dir) / "daily.md"
    text = out.read_text()
    assert text.startswith("---")
    assert "slug: daily" in text
    assert "is_active: true" in text
    assert "body here" in text


async def test_sync_lists_to_md_skips_no_slug(tmp_path):
    store = _store(list_all_lists=[{"name": "no slug"}])
    svc = _svc(tmp_path, store)
    Path(svc.lists_dir).mkdir(parents=True)
    assert await svc.sync_lists_to_md() == 0


async def test_sync_lists_to_md_skips_existing_file(tmp_path):
    store = _store(list_all_lists=[{"slug": "keep", "content_md": "new"}])
    svc = _svc(tmp_path, store)
    Path(svc.lists_dir).mkdir(parents=True)
    existing = Path(svc.lists_dir) / "keep.md"
    existing.write_text("OLD CONTENT")

    written = await svc.sync_lists_to_md()
    assert written == 0
    assert existing.read_text() == "OLD CONTENT"  # MD wins, not overwritten


# ---------------------------------------------------------------------------
# DB -> MD: sync_inbox_to_md
# ---------------------------------------------------------------------------


async def test_sync_inbox_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    svc = _svc(tmp_path)
    assert await svc.sync_inbox_to_md() == 0


async def test_sync_inbox_none_today(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    store = _store(
        get_captured_prompts=[{"content": "old", "created_at": "2020-01-01T10:00:00"}]
    )
    svc = _svc(tmp_path, store)
    assert await svc.sync_inbox_to_md() == 0


async def test_sync_inbox_writes_today(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    store = _store(
        get_captured_prompts=[
            {
                "content": "line one\nsecond",
                "created_at": "2026-07-11T14:05:00",
                "tags": ["a", "b"],
                "priority": 3,
            },
            {  # no tags, no T in timestamp -> default time
                "content": "no tags",
                "created_at": "2026-07-11",
            },
        ]
    )
    svc = _svc(tmp_path, store)
    n = await svc.sync_inbox_to_md()
    assert n == 2

    out = Path(svc.inbox_dir) / "2026" / "07" / "2026-07-11.md"
    text = out.read_text()
    assert "# Inbox 2026-07-11" in text
    assert "- [14:05] line one second #a #b (priority: 3)" in text
    assert "- [00:00] no tags (priority: 5)" in text  # default time + priority


# ---------------------------------------------------------------------------
# DB -> MD: sync_archives_to_md
# ---------------------------------------------------------------------------


async def test_sync_archives_empty(tmp_path):
    svc = _svc(tmp_path)
    assert await svc.sync_archives_to_md() == 0


async def test_sync_archives_groups_by_month(tmp_path):
    store = _store(
        get_archived_prompts={
            "prompts": [
                {
                    "content": "a\nx",
                    "category": "note",
                    "tags": ["t1"],
                    "archived_at": "2026-07-02T09:00:00",
                },
                {
                    "content": "b",
                    "category": "idea",
                    "created_at": "2026-06-15T09:00:00",  # fallback to created_at
                },
                {"content": "no date"},  # -> "unknown" bucket, skipped
            ]
        }
    )
    svc = _svc(tmp_path, store)
    total = await svc.sync_archives_to_md()
    assert total == 2  # unknown bucket excluded

    jul = (Path(svc.archive_dir) / "2026" / "07.md").read_text()
    assert "# Archive 2026-07" in jul
    assert "- [2026-07-02] [note] a x #t1" in jul

    jun = (Path(svc.archive_dir) / "2026" / "06.md").read_text()
    assert "- [2026-06-15] [idea] b" in jun


async def test_sync_archives_skips_malformed_yearmonth(tmp_path):
    # archived_at[:7] yields "2026" (only one part) -> len(parts) != 2 -> skip
    store = _store(
        get_archived_prompts={
            "prompts": [{"content": "x", "archived_at": "2026"}]
        }
    )
    svc = _svc(tmp_path, store)
    assert await svc.sync_archives_to_md() == 0


# ---------------------------------------------------------------------------
# MD -> DB: sync_md_to_lists
# ---------------------------------------------------------------------------


async def test_sync_md_to_lists_dir_missing(tmp_path):
    svc = _svc(tmp_path)  # lists_dir does not exist yet
    assert await svc.sync_md_to_lists() == 0


async def test_sync_md_to_lists_ignores_non_md_and_empty(tmp_path):
    svc = _svc(tmp_path)
    d = Path(svc.lists_dir)
    d.mkdir(parents=True)
    (d / "notes.txt").write_text("ignored")
    (d / "blank.md").write_text("   \n  ")
    assert await svc.sync_md_to_lists() == 0
    svc.prompt_store.get_list.assert_not_called()


async def test_sync_md_to_lists_creates_new(tmp_path):
    store = _store(get_list=None)
    svc = _svc(tmp_path, store)
    d = Path(svc.lists_dir)
    d.mkdir(parents=True)
    (d / "my-list.md").write_text(
        "---\ndescription: desc\ncategory: work\n---\nthe body\n"
    )

    upserted = await svc.sync_md_to_lists()
    assert upserted == 1
    store.create_list.assert_awaited_once()
    kwargs = store.create_list.await_args.kwargs
    assert kwargs["name"] == "My List"  # slug from filename -> title
    assert kwargs["category"] == "work"
    assert kwargs["content_md"] == "the body"


async def test_sync_md_to_lists_updates_existing(tmp_path):
    store = _store(get_list={"slug": "existing"})
    svc = _svc(tmp_path, store)
    d = Path(svc.lists_dir)
    d.mkdir(parents=True)
    (d / "existing.md").write_text(
        "---\nslug: existing\nname: Renamed\ndescription: dd\n"
        "category: cat\nis_active: false\n---\nupdated body\n"
    )

    upserted = await svc.sync_md_to_lists()
    assert upserted == 1
    store.create_list.assert_not_called()
    store.update_list.assert_awaited_once()
    slug_arg = store.update_list.await_args.args[0]
    fields = store.update_list.await_args.kwargs
    assert slug_arg == "existing"
    assert fields["content_md"] == "updated body"
    assert fields["name"] == "Renamed"
    assert fields["category"] == "cat"
    assert fields["is_active"] is False


async def test_sync_md_to_lists_read_error_continues(tmp_path, monkeypatch):
    store = _store(get_list=None)
    svc = _svc(tmp_path, store)
    d = Path(svc.lists_dir)
    d.mkdir(parents=True)
    (d / "bad.md").write_text("---\nname: X\n---\nbody\n")

    def _boom(_path):
        raise OSError("cannot read")

    monkeypatch.setattr(svc, "_read_file", _boom)
    # single unreadable file -> warning + continue, nothing upserted
    assert await svc.sync_md_to_lists() == 0
    store.create_list.assert_not_called()


# ---------------------------------------------------------------------------
# full_sync
# ---------------------------------------------------------------------------


async def test_full_sync_happy_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    svc = _svc(tmp_path)
    monkeypatch.setattr(svc, "sync_md_to_lists", AsyncMock(return_value=1))
    monkeypatch.setattr(svc, "sync_lists_to_md", AsyncMock(return_value=2))
    monkeypatch.setattr(svc, "sync_inbox_to_md", AsyncMock(return_value=3))
    monkeypatch.setattr(svc, "sync_archives_to_md", AsyncMock(return_value=4))

    result = await svc.full_sync()
    assert result["md_to_db_lists"] == 1
    assert result["db_to_md_lists"] == 2
    assert result["inbox_prompts"] == 3
    assert result["archive_prompts"] == 4
    assert result["errors"] == []
    assert svc.sync_count == 1
    assert svc.last_sync == FIXED_NOW
    assert svc.last_sync_result is result


async def test_full_sync_captures_each_error(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    svc = _svc(tmp_path)

    def _fail(msg):
        async def _f():
            raise RuntimeError(msg)

        return _f

    monkeypatch.setattr(svc, "sync_md_to_lists", _fail("e1"))
    monkeypatch.setattr(svc, "sync_lists_to_md", _fail("e2"))
    monkeypatch.setattr(svc, "sync_inbox_to_md", _fail("e3"))
    monkeypatch.setattr(svc, "sync_archives_to_md", _fail("e4"))

    result = await svc.full_sync()
    assert len(result["errors"]) == 4
    assert any("md_to_lists" in e for e in result["errors"])
    assert any("lists_to_md" in e for e in result["errors"])
    assert any("inbox_to_md" in e for e in result["errors"])
    assert any("archives_to_md" in e for e in result["errors"])
    assert svc.sync_count == 1  # still records the run


# ---------------------------------------------------------------------------
# Helpers: frontmatter parse / build / bool
# ---------------------------------------------------------------------------


def test_parse_frontmatter_no_marker(tmp_path):
    svc = _svc(tmp_path)
    meta, body = svc._parse_frontmatter("just body, no frontmatter")
    assert meta == {}
    assert body == "just body, no frontmatter"


def test_parse_frontmatter_no_second_marker(tmp_path):
    svc = _svc(tmp_path)
    meta, body = svc._parse_frontmatter("---\nname: X\nstill open")
    assert meta == {}
    assert body == "---\nname: X\nstill open"


def test_parse_frontmatter_types(tmp_path):
    svc = _svc(tmp_path)
    raw = (
        "---\n"
        "# a comment line\n"
        "name: 'Quoted Name'\n"
        "flag_true: yes\n"
        "flag_false: no\n"
        "active: true\n"
        "tags: [a, 'b', c]\n"
        "no_colon_line\n"
        "double: \"dq\"\n"
        "---\n"
        "the body\n"
    )
    meta, body = svc._parse_frontmatter(raw)
    assert meta["name"] == "Quoted Name"
    assert meta["flag_true"] is True
    assert meta["flag_false"] is False
    assert meta["active"] is True
    assert meta["tags"] == ["a", "b", "c"]
    assert meta["double"] == "dq"
    assert "no_colon_line" not in meta
    assert body.strip() == "the body"


def test_build_frontmatter_all_types(tmp_path):
    svc = _svc(tmp_path)
    out = svc._build_frontmatter(
        {"b": True, "f": False, "lst": ["x", "y"], "none": None, "s": "str"}
    )
    assert out.startswith("---")
    assert out.endswith("---")
    assert "b: true" in out
    assert "f: false" in out
    assert "lst: [x, y]" in out
    assert "none: " in out
    assert "s: str" in out


def test_build_then_parse_roundtrip(tmp_path):
    svc = _svc(tmp_path)
    fm = svc._build_frontmatter({"slug": "r", "active": True})
    meta, _ = svc._parse_frontmatter(fm + "\nbody")
    assert meta["slug"] == "r"
    assert meta["active"] is True


def test_parse_bool_variants(tmp_path):
    svc = _svc(tmp_path)
    assert svc._parse_bool(True) is True
    assert svc._parse_bool("YES") is True
    assert svc._parse_bool("1") is True
    assert svc._parse_bool("nope") is False
    assert svc._parse_bool(0) is False
    assert svc._parse_bool(7) is True


# ---------------------------------------------------------------------------
# Helpers: dirs / file I/O
# ---------------------------------------------------------------------------


def test_ensure_dirs(tmp_path):
    svc = _svc(tmp_path)
    svc._ensure_dirs()
    assert Path(svc.lists_dir).is_dir()
    assert Path(svc.inbox_dir).is_dir()
    assert Path(svc.archive_dir).is_dir()


def test_write_and_read_file_creates_parents(tmp_path):
    svc = _svc(tmp_path)
    target = str(tmp_path / "deep" / "nested" / "f.md")
    svc._write_file(target, "hello")
    assert svc._read_file(target) == "hello"


# ---------------------------------------------------------------------------
# get_status / get_today_inbox_md
# ---------------------------------------------------------------------------


def test_get_status_shape(tmp_path):
    svc = _svc(tmp_path)
    st = svc.get_status()
    assert st["running"] is False
    assert st["interval_seconds"] == 60
    assert st["sync_count"] == 0
    assert st["last_sync"] is None
    assert st["directories"]["lists"] == svc.lists_dir

    svc.last_sync = FIXED_NOW
    assert svc.get_status()["last_sync"] == FIXED_NOW.isoformat()


async def test_get_today_inbox_md_present_and_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ms, "utcnow_naive", lambda: FIXED_NOW)
    svc = _svc(tmp_path)
    assert await svc.get_today_inbox_md() == ""  # absent

    p = Path(svc.inbox_dir) / "2026" / "07" / "2026-07-11.md"
    p.parent.mkdir(parents=True)
    p.write_text("# Inbox 2026-07-11\n- entry\n")
    assert "entry" in await svc.get_today_inbox_md()
