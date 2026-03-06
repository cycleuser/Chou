"""
Comprehensive tests for Chou unified API, tools, and CLI flags.

Tests cover:
- ToolResult dataclass
- api.py: rename_papers()
- tools.py: TOOLS schema, dispatch()
- CLI: unified flags (-V, -v, --json, -q)
- __init__.py: public exports
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_success_result(self):
        from chou.api import ToolResult
        r = ToolResult(success=True, data={"key": "value"}, metadata={"v": "1"})
        assert r.success is True
        assert r.data == {"key": "value"}
        assert r.error is None
        assert r.metadata == {"v": "1"}

    def test_failure_result(self):
        from chou.api import ToolResult
        r = ToolResult(success=False, error="something broke")
        assert r.success is False
        assert r.data is None
        assert r.error == "something broke"

    def test_to_dict(self):
        from chou.api import ToolResult
        r = ToolResult(success=True, data=[1, 2], error=None, metadata={"x": 1})
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["success"] is True
        assert d["data"] == [1, 2]
        assert d["error"] is None
        assert d["metadata"] == {"x": 1}

    def test_default_metadata_is_independent(self):
        from chou.api import ToolResult
        r1 = ToolResult(success=True)
        r2 = ToolResult(success=True)
        r1.metadata["a"] = 1
        assert "a" not in r2.metadata


# ---------------------------------------------------------------------------
# api.py — rename_papers
# ---------------------------------------------------------------------------

class TestRenamePapersAPI:
    def test_invalid_directory(self):
        from chou.api import rename_papers
        result = rename_papers("/nonexistent/path/xyz")
        assert result.success is False
        assert "Not a directory" in result.error

    def test_invalid_author_format(self):
        from chou.api import rename_papers
        with tempfile.TemporaryDirectory() as d:
            result = rename_papers(d, author_format="bogus_format")
            assert result.success is False
            assert "Invalid author_format" in result.error

    def test_empty_directory(self):
        from chou.api import rename_papers
        with tempfile.TemporaryDirectory() as d:
            result = rename_papers(d, dry_run=True)
            assert result.success is True
            assert result.data == []
            assert result.metadata["total"] == 0

    def test_accepts_path_object(self):
        from chou.api import rename_papers
        with tempfile.TemporaryDirectory() as d:
            result = rename_papers(Path(d))
            assert result.success is True

    def test_metadata_contains_version(self):
        from chou.api import rename_papers
        with tempfile.TemporaryDirectory() as d:
            result = rename_papers(d)
            assert "version" in result.metadata

    def test_all_author_formats_accepted(self):
        from chou.api import rename_papers
        formats = ["first_surname", "first_full", "all_surnames",
                    "all_full", "n_surnames", "n_full"]
        with tempfile.TemporaryDirectory() as d:
            for fmt in formats:
                result = rename_papers(d, author_format=fmt)
                assert result.success is True, f"Failed for format: {fmt}"


# ---------------------------------------------------------------------------
# tools.py — TOOLS schema & dispatch
# ---------------------------------------------------------------------------

class TestToolsSchema:
    def test_tools_is_list(self):
        from chou.tools import TOOLS
        assert isinstance(TOOLS, list)
        assert len(TOOLS) >= 1

    def test_tool_structure(self):
        from chou.tools import TOOLS
        for tool in TOOLS:
            assert tool["type"] == "function"
            func = tool["function"]
            assert "name" in func
            assert "description" in func
            assert "parameters" in func
            params = func["parameters"]
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params

    def test_tool_name_prefix(self):
        from chou.tools import TOOLS
        for tool in TOOLS:
            assert tool["function"]["name"].startswith("chou_")

    def test_required_fields_in_properties(self):
        from chou.tools import TOOLS
        for tool in TOOLS:
            func = tool["function"]
            props = func["parameters"]["properties"]
            for req in func["parameters"]["required"]:
                assert req in props, f"Required field '{req}' not in properties"


class TestToolsDispatch:
    def test_dispatch_unknown_tool(self):
        from chou.tools import dispatch
        with pytest.raises(ValueError, match="Unknown tool"):
            dispatch("nonexistent_tool", {})

    def test_dispatch_json_string_args(self):
        from chou.tools import dispatch
        with tempfile.TemporaryDirectory() as d:
            args = json.dumps({"directory": d, "dry_run": True})
            result = dispatch("chou_rename_papers", args)
            assert isinstance(result, dict)
            assert "success" in result

    def test_dispatch_dict_args(self):
        from chou.tools import dispatch
        with tempfile.TemporaryDirectory() as d:
            result = dispatch("chou_rename_papers", {"directory": d})
            assert isinstance(result, dict)
            assert result["success"] is True

    def test_dispatch_invalid_dir(self):
        from chou.tools import dispatch
        result = dispatch("chou_rename_papers", {"directory": "/no/such/dir"})
        assert result["success"] is False
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# CLI unified flags
# ---------------------------------------------------------------------------

class TestCLIFlags:
    def _run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "chou.cli.main"] + list(args),
            capture_output=True, text=True, timeout=15,
        )

    def test_version_flag_short(self):
        r = self._run_cli("-V")
        assert r.returncode == 0
        assert "chou" in r.stdout.lower() or "瞅" in r.stdout

    def test_version_flag_long(self):
        r = self._run_cli("--version")
        assert r.returncode == 0

    def test_help_contains_json_flag(self):
        r = self._run_cli("--help")
        assert r.returncode == 0
        assert "--json" in r.stdout

    def test_help_contains_quiet_flag(self):
        r = self._run_cli("--help")
        assert "--quiet" in r.stdout or "-q" in r.stdout

    def test_help_contains_verbose_flag(self):
        r = self._run_cli("--help")
        assert "--verbose" in r.stdout or "-v" in r.stdout


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------

class TestPackageExports:
    def test_version_exported(self):
        import chou
        assert hasattr(chou, "__version__")
        assert isinstance(chou.__version__, str)

    def test_toolresult_exported(self):
        from chou import ToolResult
        r = ToolResult(success=True)
        assert r.success is True

    def test_rename_papers_exported(self):
        from chou import rename_papers
        assert callable(rename_papers)
