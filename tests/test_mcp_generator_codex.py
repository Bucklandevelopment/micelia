"""
Tests for MCPGenerator (app.services.mcp_generator).

Generates complete MCP servers (Python/FastMCP or TypeScript/@modelcontextprotocol
SDK) from a name+description+tools spec, and manages their lifecycle. Two boundaries,
both isolated here (no repo pollution, no real subprocesses):

  - **File I/O** — the generator hardcodes ``output_dir = Path("data/mcp-servers")``
    relative to cwd. ``_gen`` ``monkeypatch.chdir(tmp_path)`` **before** constructing,
    so ``__init__``'s ``mkdir`` and every write land inside pytest's sandbox; we assert
    on the real files written there.
  - **Subprocess / signals** — ``start_server``/``stop_server`` shell out via
    ``subprocess.Popen`` + ``os.setsid``/``os.getpgid``/``os.killpg``. Those names are
    monkeypatched on the ``mcp_generator`` module to fakes (``_FakeProc``) so no real
    process is ever spawned or signalled.

All public methods are synchronous, so no ``async`` markers are needed.

Covers: generate (python/typescript/unsupported, type maps, defaults, missing keys,
metadata), list_servers (empty/missing dir/non-dir/unreadable metadata/running flag),
get_server (found/no-metadata/not-found/source+files/ts), delete_server
(ok/not-found/running), start_server (ok/not-found/already-running/stale-cleanup/ts
cmd/Popen error), stop_server (ok/not-running/already-dead/timeout->kill/lookup-error),
and the get_mcp_generator singleton.
"""

import json
import signal
import subprocess
from pathlib import Path

import pytest

import app.services.mcp_generator as mg
from app.services.mcp_generator import MCPGenerator, get_mcp_generator

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOOLS_PY = [
    {
        "name": "greet",
        "description": "Greets a user",
        "parameters": [
            {"name": "who", "type": "string"},
            {"name": "times", "type": "integer", "default": 3},
            {"name": "loud", "type": "boolean", "default": False},
        ],
    },
    {"name": "ping", "description": "Ping", "parameters": []},
]


def _gen(tmp_path: Path, monkeypatch) -> MCPGenerator:
    """Construct a generator rooted inside ``tmp_path`` (via chdir)."""
    monkeypatch.chdir(tmp_path)
    return MCPGenerator()


class _FakeProc:
    """Stand-in for ``subprocess.Popen`` with a scriptable ``poll``/``wait``."""

    def __init__(self, pid=4321, poll_returns=None, wait_raises=None):
        self.pid = pid
        # poll_returns: list consumed one per call, or a scalar reused forever.
        self._poll_returns = poll_returns
        self._poll_i = 0
        self._wait_raises = wait_raises
        self.wait_calls = 0

    def poll(self):
        if isinstance(self._poll_returns, list):
            val = self._poll_returns[min(self._poll_i, len(self._poll_returns) - 1)]
            self._poll_i += 1
            return val
        return self._poll_returns

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self._wait_raises is not None:
            exc = self._wait_raises
            self._wait_raises = None  # raise once, then succeed on force-kill wait
            raise exc


# ===========================================================================
# generate() — Python
# ===========================================================================


def test_generate_python_creates_all_files_and_returns_summary(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    result = gen.generate("srv", "A server", TOOLS_PY, language="python")

    assert result == {
        "server_id": "srv",
        "path": str(gen.output_dir / "srv"),
        "language": "python",
        "tools_count": 2,
    }
    d = gen.output_dir / "srv"
    for fname in ("server.py", "pyproject.toml", "README.md", "metadata.json"):
        assert (d / fname).exists(), fname


def test_generate_python_defaults_to_python_language(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    result = gen.generate("dflt", "desc", [{"name": "t", "description": "d"}])
    assert result["language"] == "python"
    assert (gen.output_dir / "dflt" / "server.py").exists()


def test_generate_python_server_py_content(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "A server", TOOLS_PY)
    src = (gen.output_dir / "srv" / "server.py").read_text()

    assert 'mcp = FastMCP("srv")' in src
    assert "from fastmcp import FastMCP" in src
    # type mapping: string->str, integer->int, boolean->bool
    assert "who: str" in src
    assert "times: int = 3" in src
    assert "loud: bool = False" in src
    # func with no params still renders
    assert "def ping() -> str:" in src
    assert 'return f"greet called with: {who, times, loud}"' in src
    assert "mcp.run()" in src


def test_generate_python_unknown_type_falls_back_to_str(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    tools = [{"name": "t", "description": "d", "parameters": [{"name": "x", "type": "wat"}]}]
    gen.generate("srv", "d", tools)
    src = (gen.output_dir / "srv" / "server.py").read_text()
    assert "x: str" in src


def test_generate_python_missing_tool_keys_use_defaults(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    # tool with no name/description/parameters, and a param with no name
    gen.generate("srv", "d", [{"parameters": [{}]}])
    src = (gen.output_dir / "srv" / "server.py").read_text()
    assert "def unnamed_tool(arg: str) -> str:" in src
    assert "No description" in src


def test_generate_python_pyproject_and_readme(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "A server", TOOLS_PY)
    pyproject = (gen.output_dir / "srv" / "pyproject.toml").read_text()
    assert 'name = "srv"' in pyproject
    assert "fastmcp>=2.0.0" in pyproject

    readme = (gen.output_dir / "srv" / "README.md").read_text()
    assert "# srv" in readme
    assert "**greet**: Greets a user" in readme
    assert "pip install fastmcp" in readme


# ===========================================================================
# generate() — TypeScript
# ===========================================================================

TOOLS_TS = [
    {
        "name": "greet",
        "description": "Greets",
        "parameters": [
            {"name": "who", "type": "string", "description": "target"},
            {"name": "n", "type": "integer"},
            {"name": "flag", "type": "boolean"},
        ],
    },
    {"name": "noop", "description": "Nothing", "parameters": []},
]


def test_generate_typescript_creates_all_files(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    result = gen.generate("tsrv", "TS server", TOOLS_TS, language="typescript")
    assert result["language"] == "typescript"
    d = gen.output_dir / "tsrv"
    for fname in ("server.ts", "package.json", "README.md", "metadata.json"):
        assert (d / fname).exists(), fname


def test_generate_typescript_server_ts_content(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("tsrv", "TS server", TOOLS_TS, language="typescript")
    src = (gen.output_dir / "tsrv" / "server.ts").read_text()
    assert 'name: "tsrv"' in src
    assert "@modelcontextprotocol/sdk/server/mcp.js" in src
    # zod type mapping + describe
    assert 'who: z.string().describe("target")' in src
    assert "n: z.number().int()" in src
    assert "flag: z.boolean()" in src
    assert 'server.tool(\n    "greet",' in src
    assert "noop MCP server" not in src  # sanity: name only where expected


def test_generate_typescript_unknown_type_falls_back_to_zstring(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    tools = [{"name": "t", "description": "d", "parameters": [{"name": "x", "type": "wat"}]}]
    gen.generate("tsrv", "d", tools, language="typescript")
    src = (gen.output_dir / "tsrv" / "server.ts").read_text()
    assert "x: z.string()" in src


def test_generate_typescript_package_json_valid(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("tsrv", "TS server", TOOLS_TS, language="typescript")
    pkg = json.loads((gen.output_dir / "tsrv" / "package.json").read_text())
    assert pkg["name"] == "tsrv"
    assert pkg["dependencies"]["zod"] == "^3.22.0"
    assert pkg["type"] == "module"


# ===========================================================================
# generate() — errors + metadata
# ===========================================================================


def test_generate_unsupported_language_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="Unsupported language: rust"):
        gen.generate("srv", "d", [], language="rust")


def test_generate_writes_metadata_json(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "A server", TOOLS_PY, language="python")
    meta = json.loads((gen.output_dir / "srv" / "metadata.json").read_text())
    assert meta["server_id"] == "srv"
    assert meta["language"] == "python"
    assert meta["tools_count"] == 2
    assert meta["tools"] == TOOLS_PY
    assert "created_at" in meta


# ===========================================================================
# list_servers()
# ===========================================================================


def test_list_servers_empty_when_dir_absent(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    import shutil

    shutil.rmtree(gen.output_dir)
    assert gen.list_servers() == []


def test_list_servers_empty_when_no_servers(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    assert gen.list_servers() == []


def test_list_servers_reads_metadata_and_running_flag(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("a", "server a", TOOLS_PY)
    gen.generate("b", "server b", [], language="typescript")
    gen._running_processes["a"] = _FakeProc()

    servers = gen.list_servers()
    by_id = {s["server_id"]: s for s in servers}
    assert by_id["a"]["running"] is True
    assert by_id["b"]["running"] is False
    assert by_id["b"]["language"] == "typescript"


def test_list_servers_ignores_non_dir_entries(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("a", "server a", TOOLS_PY)
    (gen.output_dir / "loose_file.txt").write_text("noise")
    ids = [s["server_id"] for s in gen.list_servers()]
    assert ids == ["a"]


def test_list_servers_dir_without_metadata_skipped(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    (gen.output_dir / "orphan").mkdir()
    assert gen.list_servers() == []


def test_list_servers_unreadable_metadata_yields_fallback(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    bad = gen.output_dir / "broken"
    bad.mkdir()
    (bad / "metadata.json").write_text("{ not json ]")
    servers = gen.list_servers()
    assert len(servers) == 1
    s = servers[0]
    assert s["server_id"] == "broken"
    assert s["language"] == "unknown"
    assert s["tools_count"] == 0
    assert s["running"] is False


# ===========================================================================
# get_server()
# ===========================================================================


def test_get_server_not_found_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="nope"):
        gen.get_server("nope")


def test_get_server_returns_metadata_source_and_files(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "A server", TOOLS_PY, language="python")
    result = gen.get_server("srv")
    assert result["server_id"] == "srv"
    assert result["running"] is False
    assert "FastMCP" in result["source_code"]
    assert "server.py" in result["files"]
    assert "metadata.json" in result["files"]


def test_get_server_running_flag_true(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    gen._running_processes["srv"] = _FakeProc()
    assert gen.get_server("srv")["running"] is True


def test_get_server_typescript_reads_server_ts(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("tsrv", "d", TOOLS_TS, language="typescript")
    result = gen.get_server("tsrv")
    assert "McpServer" in result["source_code"]


def test_get_server_without_metadata_uses_minimal_dict(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    d = gen.output_dir / "bare"
    d.mkdir()
    (d / "server.py").write_text("print('hi')")
    result = gen.get_server("bare")
    assert result["server_id"] == "bare"
    assert result["source_code"] == "print('hi')"


# ===========================================================================
# delete_server()
# ===========================================================================


def test_delete_server_removes_directory(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    gen.delete_server("srv")
    assert not (gen.output_dir / "srv").exists()


def test_delete_server_not_found_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="ghost"):
        gen.delete_server("ghost")


def test_delete_server_running_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    gen._running_processes["srv"] = _FakeProc()
    with pytest.raises(RuntimeError, match="is running"):
        gen.delete_server("srv")
    assert (gen.output_dir / "srv").exists()


# ===========================================================================
# start_server()
# ===========================================================================


def _patch_popen(monkeypatch, proc, capture=None):
    """Replace mcp_generator.subprocess.Popen with a factory returning ``proc``."""

    def _factory(cmd, **kwargs):
        if capture is not None:
            capture["cmd"] = cmd
            capture["kwargs"] = kwargs
        if isinstance(proc, Exception):
            raise proc
        return proc

    monkeypatch.setattr(mg.subprocess, "Popen", _factory)
    # os.setsid is only referenced as preexec_fn; make it a no-op reference anyway
    monkeypatch.setattr(mg.os, "setsid", lambda: None, raising=False)


def test_start_server_python_spawns_and_tracks(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY, language="python")
    proc = _FakeProc(pid=999)
    cap = {}
    _patch_popen(monkeypatch, proc, cap)

    result = gen.start_server("srv")
    assert result == {"server_id": "srv", "pid": 999, "status": "running"}
    assert gen._running_processes["srv"] is proc
    assert cap["cmd"] == ["python", "server.py"]
    assert cap["kwargs"]["cwd"] == str(gen.output_dir / "srv")


def test_start_server_typescript_uses_npx(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("tsrv", "d", TOOLS_TS, language="typescript")
    cap = {}
    _patch_popen(monkeypatch, _FakeProc(), cap)
    gen.start_server("tsrv")
    assert cap["cmd"] == ["npx", "tsx", "server.ts"]


def test_start_server_not_found_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    with pytest.raises(FileNotFoundError, match="ghost"):
        gen.start_server("ghost")


def test_start_server_already_running_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    gen._running_processes["srv"] = _FakeProc(pid=111, poll_returns=None)  # poll None = alive
    with pytest.raises(RuntimeError, match="already running"):
        gen.start_server("srv")


def test_start_server_cleans_up_dead_process_then_restarts(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    gen._running_processes["srv"] = _FakeProc(pid=111, poll_returns=0)  # poll 0 = dead
    fresh = _FakeProc(pid=222)
    _patch_popen(monkeypatch, fresh)
    result = gen.start_server("srv")
    assert result["pid"] == 222
    assert gen._running_processes["srv"] is fresh


def test_start_server_no_metadata_defaults_to_python(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    (gen.output_dir / "bare").mkdir()
    cap = {}
    _patch_popen(monkeypatch, _FakeProc(), cap)
    gen.start_server("bare")
    assert cap["cmd"] == ["python", "server.py"]


def test_start_server_popen_failure_raises_runtime(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen.generate("srv", "d", TOOLS_PY)
    _patch_popen(monkeypatch, OSError("boom"))
    with pytest.raises(RuntimeError, match="Failed to start server"):
        gen.start_server("srv")
    assert "srv" not in gen._running_processes


# ===========================================================================
# stop_server()
# ===========================================================================


def _patch_signals(monkeypatch, killpg_raises=None, killpg_record=None):
    def _killpg(pgid, sig):
        if killpg_record is not None:
            killpg_record.append(sig)
        if killpg_raises is not None:
            raise killpg_raises

    monkeypatch.setattr(mg.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(mg.os, "killpg", _killpg)


def test_stop_server_not_running_raises(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="is not running"):
        gen.stop_server("srv")


def test_stop_server_already_dead_reports_already_stopped(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen._running_processes["srv"] = _FakeProc(poll_returns=0)  # already exited
    result = gen.stop_server("srv")
    assert result == {"server_id": "srv", "status": "already_stopped"}
    assert "srv" not in gen._running_processes


def test_stop_server_graceful_sigterm(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    proc = _FakeProc(pid=555, poll_returns=None)  # alive
    gen._running_processes["srv"] = proc
    sigs = []
    _patch_signals(monkeypatch, killpg_record=sigs)
    result = gen.stop_server("srv")
    assert result == {"server_id": "srv", "status": "stopped"}
    assert sigs == [signal.SIGTERM]
    assert "srv" not in gen._running_processes


def test_stop_server_timeout_escalates_to_sigkill(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    proc = _FakeProc(
        pid=555, poll_returns=None, wait_raises=subprocess.TimeoutExpired("cmd", 5)
    )
    gen._running_processes["srv"] = proc
    sigs = []
    _patch_signals(monkeypatch, killpg_record=sigs)
    result = gen.stop_server("srv")
    assert result["status"] == "stopped"
    assert sigs == [signal.SIGTERM, signal.SIGKILL]
    assert proc.wait_calls == 2  # first (timeout) + second (after kill)


def test_stop_server_process_lookup_error_swallowed(tmp_path, monkeypatch):
    gen = _gen(tmp_path, monkeypatch)
    gen._running_processes["srv"] = _FakeProc(pid=555, poll_returns=None)
    _patch_signals(monkeypatch, killpg_raises=ProcessLookupError())
    result = gen.stop_server("srv")
    assert result["status"] == "stopped"
    assert "srv" not in gen._running_processes


# ===========================================================================
# get_mcp_generator() singleton
# ===========================================================================


def test_get_mcp_generator_is_singleton(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mg, "_mcp_generator", None)
    first = get_mcp_generator()
    second = get_mcp_generator()
    assert first is second
    assert isinstance(first, MCPGenerator)
