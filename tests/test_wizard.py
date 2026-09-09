"""Tests for the interactive setup wizard helpers."""

import getpass

import pytest

from opencode_framework.wizard import suggest_branch_name


class TestSuggestBranchName:
    """Tests for per-tool config branch name suggestions."""

    def test_every_tool_gets_marked_branch(self, monkeypatch: pytest.MonkeyPatch):
        """opencode is marked like any other tool: codeagent-<user>-<tool>."""
        monkeypatch.setattr(getpass, "getuser", lambda: "alice")
        assert suggest_branch_name("opencode") == "codeagent-alice-opencode"

    def test_qwen_branch_marked(self, monkeypatch: pytest.MonkeyPatch):
        """qwen branch carries the tool suffix."""
        monkeypatch.setattr(getpass, "getuser", lambda: "alice")
        assert suggest_branch_name("qwen") == "codeagent-alice-qwen"

    def test_branches_differ_between_tools(self, monkeypatch: pytest.MonkeyPatch):
        """Two tools on one repo never suggest the same branch."""
        monkeypatch.setattr(getpass, "getuser", lambda: "bob")
        assert suggest_branch_name("opencode") != suggest_branch_name("qwen")

    def test_falls_back_to_user_when_getuser_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Unresolvable username falls back to 'user'."""

        def raise_oserror() -> str:
            raise OSError

        monkeypatch.setattr(getpass, "getuser", raise_oserror)
        assert suggest_branch_name("opencode") == "codeagent-user-opencode"

    def test_default_argument_is_opencode(self, monkeypatch: pytest.MonkeyPatch):
        """Calling without arguments uses the default tool."""
        monkeypatch.setattr(getpass, "getuser", lambda: "carol")
        assert suggest_branch_name() == suggest_branch_name("opencode")
