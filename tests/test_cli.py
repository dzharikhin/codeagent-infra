"""Tests for CLI behavior."""

import io
import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest
import typer

from opencode_framework.cli.app import (
    _build_image,
    _parse_image_name_from_build_json,
    _per_tool_image_tag,
)
from opencode_framework.exceptions import PortAllocationError


def run_cli(args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments."""
    cmd = [sys.executable, "-m", "opencode_framework"]
    if args:
        cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestVersionOutput:
    """Tests for version command output."""

    def test_version_flag_works(self):
        """--version flag should print version info."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "ocframework version:" in result.stdout

    def test_version_short_flag_works(self):
        """-v flag should print version info."""
        result = run_cli(["-v"])
        assert result.returncode == 0
        assert "ocframework version:" in result.stdout

    def test_bare_command_shows_version(self):
        """Running ocframework without args should show version."""
        result = run_cli()
        assert result.returncode == 0
        assert "ocframework version:" in result.stdout

    def test_version_shows_framework_path(self):
        """Version output should show framework repo path."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "framework repo path:" in result.stdout

    def test_version_shows_global_config_detection(self):
        """Version output should show global config detection status."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "global config found:" in result.stdout

    def test_version_shows_global_auth_detection(self):
        """Version output should show global auth.json detection status."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "global auth.json found:" in result.stdout

    def test_version_shows_global_config_path_or_expected(self):
        """Version output should show actual or expected global config path."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert (
            "global config path:" in result.stdout
            or "expected global config path:" in result.stdout
        )

    def test_version_shows_global_auth_path_or_expected(self):
        """Version output should show actual or expected global auth.json path."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert (
            "global auth.json path:" in result.stdout
            or "expected global auth.json path:" in result.stdout
        )

    def test_version_shows_qwen_settings_detection(self):
        """Version output should show qwen global settings detection status."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "qwen global settings found:" in result.stdout

    def test_version_shows_dsh_detection(self):
        """Version output should show dsh settings and credentials detection."""
        result = run_cli(["--version"])
        assert result.returncode == 0
        assert "dsh global settings found:" in result.stdout
        assert "dsh credentials found:" in result.stdout
        assert (
            "dsh global settings path:" in result.stdout
            or "expected dsh global settings path:" in result.stdout
        )
        assert (
            "dsh credentials path:" in result.stdout
            or "expected dsh credentials path:" in result.stdout
        )


class TestHelpOutput:
    """Tests for help output."""

    def test_help_flag_works(self):
        """--help should show usage information."""
        result = run_cli(["--help"])
        assert result.returncode == 0
        assert "opencode_framework" in result.stdout or "init" in result.stdout


class TestInitCommand:
    """Tests for init command."""

    def test_init_requires_git_repo(self, tmp_path: Path):
        """init should fail outside a git repo or when preflight fails."""
        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "init", "--tool", "opencode"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert (
            "not inside a Git working tree" in result.stdout
            or "not inside a Git working tree" in result.stderr
            or "Preflight failed" in result.stderr
        )


class TestLaunchCommand:
    """Tests for launch command."""

    def test_launch_requires_git_repo(self, tmp_path: Path):
        """launch should fail outside a git repo."""
        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert (
            "not inside a Git working tree" in result.stdout
            or "not inside a Git working tree" in result.stderr
        )

    def test_launch_requires_repo_root(self, tmp_path: Path):
        """launch should fail when not at repo root."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=subdir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert (
            "not the repository root" in result.stdout
            or "not the repository root" in result.stderr
        )

    def test_launch_requires_opencode_dir(self, tmp_path: Path):
        """launch should fail when .opencode doesn't exist."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert ".opencode" in result.stdout or ".opencode" in result.stderr

    def test_launch_requires_devcontainer_json(self, tmp_path: Path):
        """launch should fail when devcontainer.json doesn't exist."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        (tmp_path / ".opencode").mkdir()
        (tmp_path / ".opencode" / ".env").write_text("OCF_AGENT_TOOL=opencode\n")

        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert (
            "devcontainer.json" in result.stdout or "devcontainer.json" in result.stderr
        )

    def test_launch_requires_env_file(self, tmp_path: Path):
        """launch should fail when .env doesn't exist."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")

        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert ".env" in result.stdout or ".env" in result.stderr


class TestLaunchRebuildFeaturePrompt:
    """Tests that --rebuild wires into interactive feature management.

    Heavy runtime/docker dependencies are monkeypatched so the wiring can be
    exercised without Docker or the devcontainer CLI.
    """

    def _setup_repo(self, tmp_path: Path) -> Path:
        opencode = tmp_path / ".opencode"
        opencode.mkdir()
        (opencode / "docker-compose.yaml").write_text(
            "services:\n  opencode:\n    container_name: ocf_repo\n"
        )
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")
        return opencode

    def _patch_launch_deps(self, monkeypatch, tmp_path: Path, attach_rc=0):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            if cmd[:2] == ["docker", "attach"]:
                result.returncode = attach_rc
            elif cmd[:2] == ["docker", "compose"]:
                result.returncode = 0

            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: None)
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)
        return app_module

    def test_rebuild_invokes_update_features(self, tmp_path: Path, monkeypatch):
        """--rebuild must call update_features before building."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)

        calls = {}

        def fake_update(config_dir, repo_name, agent_tool):
            calls["args"] = (config_dir, repo_name, agent_tool)
            return False

        monkeypatch.setattr(app_module, "update_features", fake_update)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--rebuild"])

        assert result.exit_code == 0
        assert "args" in calls
        assert calls["args"][0].name == ".opencode"
        assert calls["args"][1] == tmp_path.name
        assert calls["args"][2] == "opencode"

    def test_rebuild_changed_message(self, tmp_path: Path, monkeypatch):
        """When features change, the changed message is shown."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(app_module, "update_features", lambda *a, **kw: True)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--rebuild"])

        assert result.exit_code == 0
        assert "Feature configuration changed" in result.output

    def test_rebuild_no_change_message(self, tmp_path: Path, monkeypatch):
        """When features are unchanged, the normal rebuild message is shown."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(app_module, "update_features", lambda *a, **kw: False)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--rebuild"])

        assert result.exit_code == 0
        assert "Building devcontainer image (--rebuild specified)" in result.output

    def test_no_rebuild_skips_update_features(self, tmp_path: Path, monkeypatch):
        """Without --rebuild, update_features must not be called."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(
            app_module,
            "update_features",
            lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("should not be called")
            ),
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0

    def test_launch_handles_keyboard_interrupt_in_attach(
        self, tmp_path: Path, monkeypatch
    ):
        """launch must exit silently with code 130 on SIGINT during attach."""
        self._setup_repo(tmp_path)
        attach_rc = 130
        app_module = self._patch_launch_deps(monkeypatch, tmp_path, attach_rc=attach_rc)
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())

        # Track subprocess calls
        subprocess_calls = []

        def fake_run(*args, **kwargs):
            subprocess_calls.append(("run", args, kwargs))
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            if cmd[:2] == ["docker", "attach"]:
                result.returncode = attach_rc
            elif cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = "running"
            elif cmd[:2] == ["docker", "compose"]:
                result.returncode = 0

            return result

        monkeypatch.setattr("subprocess.run", fake_run)

        from typer.testing import CliRunner

        result = CliRunner().invoke(
            app_module.app,
            ["launch", "--serve", "--port", "33050", "--hostname", "0.0.0.0"],
        )

        assert result.exit_code == 130  # Standard SIGINT exit code
        assert len(subprocess_calls) == 3  # docker inspect, docker port, docker attach

        # Verify attach was called (not docker compose run or cleanup)
        attach_call = subprocess_calls[2]
        assert "attach" in attach_call[1][0]  # args[0] is the command list


class TestLaunchAttachRemoveFeature:
    """Tests for attach/remove behavior when container already exists."""

    def _setup_repo(self, tmp_path: Path) -> Path:
        opencode = tmp_path / ".opencode"
        opencode.mkdir()
        (opencode / "docker-compose.yaml").write_text(
            "services:\n  opencode:\n    container_name: ocf_repo\n"
        )
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")
        return opencode

    def _patch_launch_deps(
        self,
        monkeypatch,
        tmp_path: Path,
        attach_rc=0,
        inspect_status="running",
        port_output="",
    ):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

            if cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = inspect_status if inspect_status else "running"
            elif cmd[:2] == ["docker", "port"]:
                result.stdout = port_output
            elif cmd[:2] == ["docker", "attach"]:
                result.returncode = attach_rc
            elif cmd[:2] == ["docker", "rm"] and "-f" in cmd:
                result.returncode = 0
            elif cmd[:2] == ["docker", "compose"]:
                result.returncode = 0

            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: None)
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)
        return app_module

    def test_launch_attaches_when_running(self, tmp_path: Path, monkeypatch):
        """launch must attach to running container instead of starting new one."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=0, inspect_status="running"
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0
        assert "attaching" in result.output.lower()

    def test_launch_attach_failure_prints_force_hint(self, tmp_path: Path, monkeypatch):
        """When attach fails, print error and --force hint."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=1, inspect_status="running"
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 1
        assert "Failed to attach" in result.output
        assert "--force" in result.output

    def test_launch_attach_interrupted_silent(self, tmp_path: Path, monkeypatch):
        """When attach exits with SIGINT (130), exit silently with code 130."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=130, inspect_status="running"
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 130
        assert "Failed to attach" not in result.output
        assert "--force" not in result.output

    def test_launch_removes_stopped_container(self, tmp_path: Path, monkeypatch):
        """Stopped container must be removed before starting new one."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=125, inspect_status="exited"
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0

    def test_launch_force_removes_running_container(self, tmp_path: Path, monkeypatch):
        """--force must remove running container before starting new one."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=0, inspect_status="running"
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--force"])

        assert result.exit_code == 0

    def test_launch_no_container_runs_normally(self, tmp_path: Path, monkeypatch):
        """When no container exists, launch runs normally."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=0, inspect_status=None
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0

    def test_launch_force_removes_image_id(self, tmp_path: Path, monkeypatch):
        """--force must delete .image_id and trigger a rebuild."""
        self._setup_repo(tmp_path)
        image_id_path = tmp_path / ".opencode" / "runtime_data" / ".image_id"
        image_id_path.parent.mkdir(parents=True, exist_ok=True)
        image_id_path.write_text("sha256:stale")

        build_calls = []
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=0, inspect_status=None
        )
        monkeypatch.setattr(
            app_module,
            "_build_image",
            lambda *a, **kw: build_calls.append(True) or "sha256:new",
        )
        # real load_image_id so it reflects the deleted file
        import opencode_framework.sandbox.runtime as rt_module

        monkeypatch.setattr(app_module, "load_image_id", rt_module.load_image_id)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--force"])

        assert result.exit_code == 0
        assert not image_id_path.exists()
        assert "Removed cached image ID" in result.output
        assert "Building devcontainer image" in result.output
        assert len(build_calls) == 1

    def test_launch_force_skips_update_features(self, tmp_path: Path, monkeypatch):
        """--force must not invoke the interactive feature reselection prompt."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch, tmp_path, attach_rc=0, inspect_status=None
        )
        monkeypatch.setattr(
            app_module,
            "update_features",
            lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError("update_features must not be called with --force")
            ),
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--force"])

        assert result.exit_code == 0

    def test_launch_attach_prints_port_mappings(self, tmp_path: Path, monkeypatch):
        """Port mappings must be shown when attaching to a running container."""
        self._setup_repo(tmp_path)
        port_output = "4096/tcp -> 0.0.0.0:4096\n8080/tcp -> 0.0.0.0:8080"
        app_module = self._patch_launch_deps(
            monkeypatch,
            tmp_path,
            attach_rc=0,
            inspect_status="running",
            port_output=port_output,
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0
        assert "Port mappings:" in result.output
        assert "4096/tcp -> 0.0.0.0:4096" in result.output
        assert "8080/tcp -> 0.0.0.0:8080" in result.output

    def test_launch_attach_no_ports_skips_mapping_section(
        self, tmp_path: Path, monkeypatch
    ):
        """No port mapping section when the running container has no published ports."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(
            monkeypatch,
            tmp_path,
            attach_rc=0,
            inspect_status="running",
            port_output="",
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0
        assert "Port mappings:" not in result.output
        assert "attaching" in result.output.lower()


class TestLaunchServer:
    """Tests for the --server option of ``ocframework launch``."""

    def _setup_repo(self, tmp_path: Path, ports_block: str = "") -> Path:
        opencode = tmp_path / ".opencode"
        opencode.mkdir()
        compose = "services:\n  opencode:\n    container_name: ocf_repo\n"
        if ports_block:
            compose += ports_block
        (opencode / "docker-compose.yaml").write_text(compose)
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")
        return opencode

    def _patch_launch_deps(self, monkeypatch, tmp_path: Path):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        captured: list = []

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = ""  # no container
            elif cmd[:2] == ["docker", "compose"] and "run" in cmd:
                captured.append(cmd)
                result.returncode = 0
            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)
        return app_module, captured

    def test_launch_without_server_uses_opencode_tui(self, tmp_path: Path, monkeypatch):
        """Without --server, launch runs the opencode TUI (no --publish)."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0
        assert len(captured) == 1
        assert captured[0][-1] == "opencode"
        assert "--publish" not in captured[0]

    def test_launch_server_bare_picks_free_port(self, tmp_path: Path, monkeypatch):
        """Bare --server picks the first free port and runs opencode serve."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(
            app_module, "find_free_port", lambda s, e, reserved=None: 4096
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server"])

        assert result.exit_code == 0
        assert "Auto-assigned server port: 4096" in result.output
        assert len(captured) == 1
        cmd = captured[0]
        assert "--publish" in cmd
        idx = cmd.index("--publish")
        assert cmd[idx + 1] == "4096:4096"
        tail = cmd[-6:]
        assert tail == ["opencode", "serve", "--hostname", "0.0.0.0", "--port", "4096"]

    def test_launch_server_explicit_port_eq(self, tmp_path: Path, monkeypatch):
        """--server=N forces host port N."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert len(captured) == 1
        cmd = captured[0]
        idx = cmd.index("--publish")
        assert cmd[idx + 1] == "5000:4096"

    def test_launch_server_explicit_port_space(self, tmp_path: Path, monkeypatch):
        """--server N (space-separated) forces host port N."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server", "5000"])

        assert result.exit_code == 0
        assert len(captured) == 1
        cmd = captured[0]
        idx = cmd.index("--publish")
        assert cmd[idx + 1] == "5000:4096"

    def test_launch_server_invalid_port_string(self, tmp_path: Path, monkeypatch):
        """--server=notanumber exits 1 with an error message."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=notanumber"])

        assert result.exit_code == 1
        assert "invalid --server port" in result.output

    def test_launch_server_out_of_range(self, tmp_path: Path, monkeypatch):
        """--server=99999 exits 1 (port out of range)."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=99999"])

        assert result.exit_code == 1

    def test_launch_server_no_free_port(self, tmp_path: Path, monkeypatch):
        """Bare --server exits 1 when no free port is available."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        def raise_no_port(s, e, reserved=None):
            raise PortAllocationError(message="no free port", remediation="free some")

        monkeypatch.setattr(app_module, "find_free_port", raise_no_port)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server"])

        assert result.exit_code == 1
        assert "free some" in result.output

    def test_launch_server_conflicts_with_pass_through_serve(
        self, tmp_path: Path, monkeypatch
    ):
        """--server conflicts with explicit 'serve' in pass-through args."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(
            app_module.app, ["launch", "--server", "--", "serve"]
        )

        assert result.exit_code == 1
        assert "conflicts with 'serve'" in result.output

    def test_launch_server_republishes_wizard_ports(self, tmp_path: Path, monkeypatch):
        """--server republishes wizard ports individually instead of --service-ports."""
        self._setup_repo(tmp_path, ports_block="    ports:\n      - 8080:8080\n")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert len(captured) == 1
        cmd = captured[0]
        assert "--service-ports" not in cmd
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert "8080:8080" in publish_pairs
        assert "5000:4096" in publish_pairs

    def test_launch_server_republishes_wizard_ports_with_protocol(
        self, tmp_path: Path, monkeypatch
    ):
        """--server preserves protocol suffix on republished wizard ports."""
        self._setup_repo(tmp_path, ports_block="    ports:\n      - 8443:443/tcp\n")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 0
        cmd = captured[0]
        assert "--service-ports" not in cmd
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert "8443:443/tcp" in publish_pairs
        assert "5000:4096" in publish_pairs

    def test_launch_server_without_wizard_ports_emits_only_server_publish(
        self, tmp_path: Path, monkeypatch
    ):
        """--server with no wizard ports emits only the server --publish."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 0
        cmd = captured[0]
        assert "--service-ports" not in cmd
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert publish_pairs == ["5000:4096"]

    def test_launch_server_explicit_port_conflicts_with_wizard_port(
        self, tmp_path: Path, monkeypatch
    ):
        """--server=N exits 1 with a clear message when N matches a wizard port."""
        self._setup_repo(tmp_path, ports_block="    ports:\n      - 5000:5000\n")
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 1
        assert "conflicts with a compose port mapping" in result.output

    def test_launch_server_bare_skips_wizard_ports_when_auto_picking(
        self, tmp_path: Path, monkeypatch
    ):
        """Bare --server passes wizard host ports as reserved to find_free_port."""
        self._setup_repo(tmp_path, ports_block="    ports:\n      - 4096:4096\n")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        reserved_received: list = []

        def capture_reserved(s, e, reserved=None):
            reserved_received.extend(reserved or [])
            return 4097

        monkeypatch.setattr(app_module, "find_free_port", capture_reserved)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server"])

        assert result.exit_code == 0
        assert 4096 in reserved_received
        cmd = captured[0]
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert "4097:4096" in publish_pairs

    def test_launch_server_echoes_url(self, tmp_path: Path, monkeypatch):
        """--server echoes the URL where opencode serve will be available."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert "http://127.0.0.1:5000" in result.output
        assert "Auto-assigned" not in result.output

    def test_launch_serve_typo_not_matched_as_server(self, tmp_path: Path, monkeypatch):
        """--serve (typo) must not be consumed as --server."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--", "--serve"])

        assert result.exit_code == 0
        assert len(captured) == 1
        # --server not detected → no --publish
        assert "--publish" not in captured[0]
        # --serve leaked to container command as pass-through
        assert "--serve" in captured[0]

    def test_launch_server_port_zero_rejected(self, tmp_path: Path, monkeypatch):
        """--server=0 exits 1 (port 0 not allowed; must echo a real URL)."""
        self._setup_repo(tmp_path)
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server=0"])

        assert result.exit_code == 1
        assert "invalid --server port" in result.output

    def test_launch_server_tokens_do_not_leak_to_container(
        self, tmp_path: Path, monkeypatch
    ):
        """Consumed --server and its value must not appear in container command."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch", "--server", "5000"])

        assert result.exit_code == 0
        assert len(captured) == 1
        cmd = captured[0]
        opencode_idx = cmd.index("opencode")
        container_cmd = cmd[opencode_idx:]
        assert "--server" not in container_cmd
        assert "5000" not in container_cmd

    def test_launch_server_bare_before_other_flag(self, tmp_path: Path, monkeypatch):
        """--server followed by a non-numeric flag treats --server as bare."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(
            app_module, "find_free_port", lambda s, e, reserved=None: 4096
        )

        from typer.testing import CliRunner

        result = CliRunner().invoke(
            app_module.app, ["launch", "--server", "--", "--other-flag"]
        )

        assert result.exit_code == 0
        assert len(captured) == 1
        cmd = captured[0]
        idx = cmd.index("--publish")
        assert cmd[idx + 1] == "4096:4096"
        # --other-flag leaks through as pass-through arg
        assert "--other-flag" in cmd


class _InterruptingReader(io.BytesIO):
    """BytesIO whose readline raises KeyboardInterrupt (simulates Ctrl+C)."""

    def readline(self, *args, **kwargs):
        raise KeyboardInterrupt


class _FakeAcpChild:
    """Minimal subprocess.Popen stand-in for ACP launch tests."""

    def __init__(
        self,
        stdout: bytes = b"",
        returncode: int = 0,
        interrupt_on_read: bool = False,
    ):
        if interrupt_on_read:
            self.stdout: io.BytesIO = _InterruptingReader(stdout)
        else:
            self.stdout = io.BytesIO(stdout)
        self._returncode = returncode
        self.terminated = False

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True

    def wait(self, timeout=None):
        return self._returncode

    @property
    def returncode(self):
        return self._returncode


class TestLaunchAcp:
    """Tests for the --acp option of ``ocframework launch``."""

    def _setup_repo(
        self,
        tmp_path: Path,
        tool: str = "opencode",
        ports_block: str = "",
    ) -> Path:
        dirname = {"dsh": ".dsh", "qwen": ".qwen"}.get(tool, ".opencode")
        config = tmp_path / dirname
        config.mkdir()
        compose = f"services:\n  {tool}:\n    container_name: ocf_repo\n"
        if ports_block:
            compose += ports_block
        (config / "docker-compose.yaml").write_text(compose)
        (config / ".env").write_text(f"REMOTE_USER=root\nOCF_AGENT_TOOL={tool}\n")
        return config

    def _patch_launch_deps(
        self,
        monkeypatch,
        tmp_path: Path,
        tool: str = "opencode",
        child: _FakeAcpChild = None,
        container_status: str = "",
    ):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        captured: list = []
        cleanups: list = []
        redirected: list = []
        popen_envs: list = []
        child = child if child is not None else _FakeAcpChild()

        def fake_popen(cmd, **kw):
            captured.append(list(cmd))
            popen_envs.append(kw.get("env", {}))
            return child

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = container_status
            return result

        def fake_redirect():
            redirected.append(True)
            return io.BytesIO()

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(
            app_module,
            "load_env_with_overrides",
            lambda **kw: {"OCF_AGENT_TOOL": tool},
        )
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(app_module, "_acp_redirect_stdout_to_stderr", fake_redirect)
        real_cleanup = app_module._compose_cleanup

        def recording_cleanup(name, compose_path, env):
            cleanups.append(name)
            real_cleanup(name, compose_path, env)

        monkeypatch.setattr(app_module, "_compose_cleanup", recording_cleanup)
        monkeypatch.chdir(tmp_path)
        return app_module, captured, cleanups, redirected, popen_envs

    def _invoke(self, app_module, args: list):
        from typer.testing import CliRunner

        return CliRunner().invoke(app_module.app, args)

    def test_acp_command_shape(self, tmp_path: Path, monkeypatch):
        """--acp runs opencode acp with -T, no TTY flags, and no publishing."""
        self._setup_repo(tmp_path)
        app_module, captured, _, redirected, _ = self._patch_launch_deps(
            monkeypatch, tmp_path
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        assert redirected == [True]
        assert len(captured) == 1
        cmd = captured[0]
        assert cmd[:6] == ["docker", "compose", "-f", cmd[3], "run", "--rm"]
        assert "-T" in cmd
        name_idx = cmd.index("--name")
        assert cmd[name_idx + 1] == "ocf_repo_zed"
        assert "--service-ports" not in cmd
        assert "--publish" not in cmd
        assert cmd[-2:] == ["opencode", "acp"]

    def test_acp_qwen_command_tail(self, tmp_path: Path, monkeypatch):
        """--acp with qwen appends the qwen --acp flag."""
        self._setup_repo(tmp_path, tool="qwen")
        app_module, captured, _, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, tool="qwen"
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        assert captured[0][-2:] == ["qwen", "--acp"]

    def test_acp_pass_through_args_reach_container(self, tmp_path: Path, monkeypatch):
        """Args after -- pass through to the ACP agent command."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(
            app_module, ["launch", "--acp", "zed", "--", "debug", "config"]
        )

        assert result.exit_code == 0
        assert captured[0][-4:] == ["opencode", "acp", "debug", "config"]

    def test_acp_sets_session_suffix_env(self, tmp_path: Path, monkeypatch):
        """ACP launch exports OCF_SESSION_SUFFIX=_<postfix> to the child."""
        self._setup_repo(tmp_path)
        app_module, _, _, _, popen_envs = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        assert popen_envs
        assert popen_envs[0]["OCF_SESSION_SUFFIX"] == "_zed"

    def test_plain_launch_omits_session_suffix_env(self, tmp_path: Path, monkeypatch):
        """Plain launch strips OCF_SESSION_SUFFIX so shared volumes stay bare."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)
        run_envs: list = []
        real_mock_run = app_module.subprocess.run

        def recording_run(*args, **kw):
            cmd = list(args[0]) if args else []
            if cmd[:2] == ["docker", "compose"] and "run" in cmd:
                run_envs.append(dict(kw.get("env", {})))
                captured.append(cmd)
            return real_mock_run(*args, **kw)

        monkeypatch.setattr(app_module.subprocess, "run", recording_run)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert run_envs
        assert "OCF_SESSION_SUFFIX" not in run_envs[0]

    def test_acp_skips_service_ports_with_wizard_ports(
        self, tmp_path: Path, monkeypatch
    ):
        """--acp neither republishes wizard ports nor uses --service-ports."""
        self._setup_repo(tmp_path, ports_block="    ports:\n      - 8080:8080\n")
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        cmd = captured[0]
        assert "--service-ports" not in cmd
        assert "--publish" not in cmd

    def test_acp_exit_code_forwarded(self, tmp_path: Path, monkeypatch):
        """launch exits with the ACP session's exit code."""
        self._setup_repo(tmp_path)
        child = _FakeAcpChild(returncode=7)
        app_module, captured, _, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, child=child
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 7
        assert len(captured) == 1

    def test_acp_signal_death_maps_to_143(self, tmp_path: Path, monkeypatch):
        """A child killed by SIGTERM (-15) exits 143 and cleans up."""
        self._setup_repo(tmp_path)
        child = _FakeAcpChild(returncode=-15)
        app_module, captured, cleanups, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, child=child
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 143
        assert cleanups == ["ocf_repo_zed"]
        assert len(captured) == 1

    def test_acp_keyboard_interrupt_terminates_and_cleans_up(
        self, tmp_path: Path, monkeypatch
    ):
        """Ctrl+C during the ACP session terminates the child and exits 130."""
        self._setup_repo(tmp_path)
        child = _FakeAcpChild(interrupt_on_read=True)
        app_module, captured, cleanups, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, child=child
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 130
        assert child.terminated
        assert cleanups == ["ocf_repo_zed"]
        assert len(captured) == 1

    def test_acp_replaces_running_container(self, tmp_path: Path, monkeypatch):
        """--acp never attaches: existing container is removed for a fresh run."""
        self._setup_repo(tmp_path)
        app_module, captured, cleanups, redirected, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, container_status="running"
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        assert redirected == [True]
        assert len(captured) == 1
        assert "Removing existing container 'ocf_repo_zed'" in result.output
        assert "Removed container 'ocf_repo_zed'" in result.output
        assert cleanups == []

    def test_acp_replaces_stopped_container(self, tmp_path: Path, monkeypatch):
        """--acp removes a stopped container too and starts a session."""
        self._setup_repo(tmp_path)
        app_module, captured, _, redirected, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, container_status="exited"
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 0
        assert redirected == [True]
        assert len(captured) == 1
        assert "Removing existing container 'ocf_repo_zed'" in result.output

    def test_acp_removal_failure_is_fatal(self, tmp_path: Path, monkeypatch):
        """--acp aborts when the existing container cannot be removed."""
        self._setup_repo(tmp_path)
        app_module, captured, cleanups, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, container_status="running"
        )
        monkeypatch.setattr(app_module, "_remove_container", lambda name, env: False)

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 1
        assert "failed to remove container 'ocf_repo_zed'" in result.output
        assert "docker rm -f ocf_repo_zed" in result.output
        assert captured == []
        assert cleanups == []

    def test_acp_force_removes_running_container(self, tmp_path: Path, monkeypatch):
        """--acp --force removes the running container and starts a session."""
        self._setup_repo(tmp_path)
        app_module, captured, _, redirected, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, container_status="running"
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed", "--force"])

        assert result.exit_code == 0
        assert redirected == [True]
        assert len(captured) == 1

    def test_acp_requires_postfix(self, tmp_path: Path, monkeypatch):
        """Bare --acp is a usage error: the postfix value is required."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp"])

        assert result.exit_code == 2
        assert "requires an argument" in result.output
        assert captured == []

    def test_acp_rejects_invalid_postfix(self, tmp_path: Path, monkeypatch):
        """A postfix outside the docker name charset is rejected."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "bad postfix!"])

        assert result.exit_code == 1
        assert "invalid --acp postfix" in result.output
        assert captured == []

    def test_acp_leading_flag_becomes_invalid_postfix(
        self, tmp_path: Path, monkeypatch
    ):
        """--acp --server: click consumes the flag as the value; rejected."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "--server"])

        assert result.exit_code == 1
        assert "invalid --acp postfix" in result.output
        assert captured == []

    def test_acp_requires_container_name_in_compose(self, tmp_path: Path, monkeypatch):
        """ACP needs a deterministic base name: missing container_name is fatal."""
        config = tmp_path / ".opencode"
        config.mkdir()
        (config / "docker-compose.yaml").write_text(
            "services:\n  opencode:\n    image: busybox\n"
        )
        (config / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 1
        assert "container_name" in result.output
        assert "init --force" in result.output
        assert captured == []

    def test_acp_rejected_for_dsh(self, tmp_path: Path, monkeypatch):
        """dsh has no ACP mode: hard error with a --server remediation."""
        self._setup_repo(tmp_path, tool="dsh")
        app_module, captured, _, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path, tool="dsh"
        )

        result = self._invoke(app_module, ["launch", "--acp", "zed"])

        assert result.exit_code == 1
        assert "does not support ACP mode" in result.output
        assert "--server" in result.output
        assert captured == []

    def test_acp_rejects_server_combination(self, tmp_path: Path, monkeypatch):
        """--acp and --server are mutually exclusive."""
        self._setup_repo(tmp_path)
        app_module, captured, _, _, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--acp", "zed", "--server"])

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output
        assert captured == []

    def test_plain_launch_keyboard_interrupt_cleans_up(
        self, tmp_path: Path, monkeypatch
    ):
        """Regression: plain launch Ctrl+C still cleans up and exits 130."""
        self._setup_repo(tmp_path)
        app_module, captured, cleanups, _, _ = self._patch_launch_deps(
            monkeypatch, tmp_path
        )
        cleanups.clear()  # reuse the recorder, not the Popen path

        def raising_run(*args, **kw):
            cmd = list(args[0]) if args else []
            if cmd[:2] == ["docker", "compose"] and "run" in cmd:
                raise KeyboardInterrupt
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            return result

        monkeypatch.setattr(app_module.subprocess, "run", raising_run)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 130
        assert "Interrupted. Cleaning up container..." in result.output
        assert "Cleanup complete." in result.output

    def test_pump_routes_envelope_and_chatter(self):
        """_pump_acp_stdout sends JSON-RPC envelopes to stdout, chatter to stderr."""
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        child = _FakeAcpChild(
            stdout=(
                b'  {"jsonrpc":"2.0","id":1}\n'
                b"[cost-guard] Active\n"
                b'{"jsonrpc":"2.0","id":2}\n'
            )
        )
        out = io.BytesIO()
        err = io.BytesIO()

        app_module._pump_acp_stdout(child, out, err)

        assert out.getvalue() == (
            b'  {"jsonrpc":"2.0","id":1}\n{"jsonrpc":"2.0","id":2}\n'
        )
        assert err.getvalue() == b"[cost-guard] Active\n"

    def test_session_forwards_exit_code(self, monkeypatch):
        """_run_acp_session exits with the child's return code, no cleanup."""
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        cleanups: list = []
        monkeypatch.setattr(
            app_module, "_compose_cleanup", lambda *a: cleanups.append(a[0])
        )
        child = _FakeAcpChild(stdout=b'{"jsonrpc":"2.0"}\n', returncode=7)

        with pytest.raises(typer.Exit) as exc_info:
            app_module._run_acp_session(
                child, io.BytesIO(), Path("docker-compose.yaml"), "ocf_repo", {}
            )

        assert exc_info.value.exit_code == 7
        assert cleanups == []
        assert not child.terminated

    def test_session_sigterm_terminates_child(self, monkeypatch):
        """The SIGTERM handler installed by _run_acp_session stops the child."""
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        terminated: list = []
        cleanups: list = []
        monkeypatch.setattr(
            app_module, "_terminate_acp_child", lambda p: terminated.append(p)
        )
        monkeypatch.setattr(
            app_module, "_compose_cleanup", lambda *a: cleanups.append(a)
        )
        child = _FakeAcpChild()

        def pump_then_sigterm(process, out, err):
            os.kill(os.getpid(), signal.SIGTERM)

        monkeypatch.setattr(app_module, "_pump_acp_stdout", pump_then_sigterm)
        previous = signal.getsignal(signal.SIGTERM)
        try:
            with pytest.raises(typer.Exit) as exc_info:
                app_module._run_acp_session(
                    child, io.BytesIO(), Path("docker-compose.yaml"), "ocf_repo", {}
                )
        finally:
            signal.signal(signal.SIGTERM, previous)

        assert exc_info.value.exit_code == 0
        assert terminated == [child]
        assert cleanups == []

    def test_session_interrupt_cleans_up(self, monkeypatch):
        """A KeyboardInterrupt inside the session exits 130 after cleanup."""
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        cleanups: list = []
        monkeypatch.setattr(
            app_module, "_compose_cleanup", lambda *a: cleanups.append(a[0])
        )
        child = _FakeAcpChild(interrupt_on_read=True)

        with pytest.raises(typer.Exit) as exc_info:
            app_module._run_acp_session(
                child, io.BytesIO(), Path("docker-compose.yaml"), "ocf_repo", {}
            )

        assert exc_info.value.exit_code == 130
        assert cleanups == ["ocf_repo"]
        assert child.terminated


class TestInitToolOption:
    """Tests for the init --tool option."""

    def test_init_rejects_unknown_tool(self):
        """init --tool bogus exits 1 with remediation before preflight."""
        import importlib

        from typer.testing import CliRunner

        app_module = importlib.import_module("opencode_framework.cli.app")
        result = CliRunner().invoke(app_module.app, ["init", "--tool", "bogus"])

        assert result.exit_code == 1
        assert "Unsupported agent tool" in result.output
        assert "dsh, opencode, qwen" in result.output
        assert "Preflight" not in result.output


class TestLaunchToolSpec:
    """Tests for per-tool launch behavior driven by OCF_AGENT_TOOL."""

    def _setup_repo(self, tmp_path: Path, service: str = "opencode") -> Path:
        dirname = {"dsh": ".dsh", "qwen": ".qwen"}.get(service, ".opencode")
        config = tmp_path / dirname
        config.mkdir()
        (config / "docker-compose.yaml").write_text(
            f"services:\n  {service}:\n    container_name: ocf_repo\n"
        )
        (config / ".env").write_text(f"REMOTE_USER=root\nOCF_AGENT_TOOL={service}\n")
        return config

    def _patch_launch_deps(self, monkeypatch, tmp_path: Path, tool_env=None):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        captured: list = []

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = ""  # no container
            elif cmd[:2] == ["docker", "compose"] and "run" in cmd:
                captured.append(cmd)
                result.returncode = 0
            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(
            app_module,
            "load_env_with_overrides",
            lambda **kw: dict(tool_env or {}),
        )
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)
        return app_module, captured

    @staticmethod
    def _env_pairs(cmd: list) -> list:
        return [cmd[i + 1] for i, t in enumerate(cmd) if t == "--env"]

    def _invoke(self, app_module, args: list):
        from typer.testing import CliRunner

        return CliRunner().invoke(app_module.app, args)

    def test_qwen_tui_uses_qwen_binary(self, tmp_path: Path, monkeypatch):
        """OCF_AGENT_TOOL=qwen runs the qwen binary."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "qwen"}
        )

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert len(captured) == 1
        assert captured[0][-1] == "qwen"
        assert "--publish" not in captured[0]

    def test_qwen_server_command_and_port(self, tmp_path: Path, monkeypatch):
        """--server with qwen publishes to 4170 and runs 'qwen serve'."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "qwen"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        cmd = captured[0]
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert "5000:4170" in publish_pairs
        tail = cmd[-6:]
        assert tail == ["qwen", "serve", "--hostname", "0.0.0.0", "--port", "4170"]

    def test_qwen_server_generates_and_injects_token(self, tmp_path: Path, monkeypatch):
        """qwen --server generates a 64-hex token, injects and echoes it."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "qwen"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        cmd = captured[0]
        token_pairs = [
            p for p in self._env_pairs(cmd) if p.startswith("QWEN_SERVER_TOKEN=")
        ]
        assert len(token_pairs) == 1
        token = token_pairs[0].split("=", 1)[1]
        assert len(token) == 64
        assert all(c in "0123456789abcdef" for c in token)
        assert "Web Shell token (QWEN_SERVER_TOKEN)" in result.output
        # The token must not leak into the container command tail
        container_cmd = cmd[cmd.index("qwen") :]
        assert token not in container_cmd

    def test_opencode_server_generates_no_token(self, tmp_path: Path, monkeypatch):
        """opencode (no token_required) gets no auto-generated password."""
        self._setup_repo(tmp_path)
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert not any(
            p.startswith("OPENCODE_SERVER_PASSWORD=")
            for p in self._env_pairs(captured[0])
        )

    def test_user_supplied_token_preserved(self, tmp_path: Path, monkeypatch):
        """A user-provided QWEN_SERVER_TOKEN is used verbatim, not regenerated."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, captured = self._patch_launch_deps(
            monkeypatch,
            tmp_path,
            {"OCF_AGENT_TOOL": "qwen", "QWEN_SERVER_TOKEN": "user-token"},
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert "QWEN_SERVER_TOKEN=user-token" in self._env_pairs(captured[0])
        assert "Web Shell token" not in result.output

    def test_invalid_agent_tool_env_exits(self, tmp_path: Path, monkeypatch):
        """A .env contradicting its directory exits 1 with a re-init remediation."""
        self._setup_repo(tmp_path)
        opencode = tmp_path / ".opencode"
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=nope\n")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 1
        assert "OCF_AGENT_TOOL='nope'" in result.output
        assert ".opencode/ is the opencode config directory" in result.output
        assert "init --force --tool opencode" in result.output
        assert captured == []

    def test_missing_agent_tool_env_exits(self, tmp_path: Path, monkeypatch):
        """A .env without OCF_AGENT_TOOL exits 1 with a re-init remediation."""
        self._setup_repo(tmp_path)
        opencode = tmp_path / ".opencode"
        (opencode / ".env").write_text("REMOTE_USER=root\n")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 1
        assert "does not set OCF_AGENT_TOOL" in result.output
        assert "init --force --tool opencode" in result.output
        assert captured == []

    def test_global_env_path_follows_opencode_tool(self, tmp_path: Path, monkeypatch):
        """launch loads the global .env from the opencode tool's path."""
        self._setup_repo(tmp_path)
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)
        load_calls: list = []

        def fake_load(**kw):
            load_calls.append(kw)
            return {"REMOTE_USER": "root"}

        monkeypatch.setattr(app_module, "load_env_with_overrides", fake_load)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert len(load_calls) == 1
        assert str(load_calls[0]["global_env_path"]).endswith("opencode/.env")

    def test_global_env_path_follows_qwen_tool(self, tmp_path: Path, monkeypatch):
        """launch loads the global .env from the qwen tool's path."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)
        load_calls: list = []

        def fake_load(**kw):
            load_calls.append(kw)
            return {"REMOTE_USER": "root"}

        monkeypatch.setattr(app_module, "load_env_with_overrides", fake_load)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert len(load_calls) == 1
        assert str(load_calls[0]["global_env_path"]).endswith(".qwen/.env")

    def test_qwen_server_url_wording(self, tmp_path: Path, monkeypatch):
        """--server with qwen echoes the qwen serve URL."""
        self._setup_repo(tmp_path, service="qwen")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "qwen"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert "qwen serve will be available at http://127.0.0.1:5000" in result.output

    def test_dsh_bare_launch_runs_bare_binary(self, tmp_path: Path, monkeypatch):
        """Plain dsh launch runs bare `dsh` (documented usage-error dead end)."""
        self._setup_repo(tmp_path, service="dsh")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "dsh"}
        )

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert len(captured) == 1
        assert captured[0][-1] == "dsh"
        assert "--publish" not in captured[0]

    def test_dsh_server_command_and_port(self, tmp_path: Path, monkeypatch):
        """--server with dsh publishes to 3080 and runs the web serve args."""
        self._setup_repo(tmp_path, service="dsh")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "dsh"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        cmd = captured[0]
        publish_pairs = [cmd[i + 1] for i, t in enumerate(cmd) if t == "--publish"]
        assert "5000:3080" in publish_pairs
        tail = cmd[-7:]
        assert tail == [
            "dsh",
            "web",
            "--patch",
            "/opt/ocframework/config/dsh/web-bind-all.patch.yml",
            "--no-open",
            "--port",
            "3080",
        ]

    def test_dsh_server_generates_no_token(self, tmp_path: Path, monkeypatch):
        """dsh manages its own one-time URL token; the framework injects none."""
        self._setup_repo(tmp_path, service="dsh")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "dsh"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert "Web Shell token" not in result.output
        assert not any(p.startswith("=") for p in self._env_pairs(captured[0]))

    def test_dsh_server_url_wording(self, tmp_path: Path, monkeypatch):
        """--server with dsh echoes the dsh serve URL."""
        self._setup_repo(tmp_path, service="dsh")
        app_module, captured = self._patch_launch_deps(
            monkeypatch, tmp_path, {"OCF_AGENT_TOOL": "dsh"}
        )

        result = self._invoke(app_module, ["launch", "--server=5000"])

        assert result.exit_code == 0
        assert "dsh serve will be available at http://127.0.0.1:5000" in result.output

    def test_global_env_path_follows_dsh_tool(self, tmp_path: Path, monkeypatch):
        """launch loads the global .env from the dsh tool's path."""
        self._setup_repo(tmp_path, service="dsh")
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)
        load_calls: list = []

        def fake_load(**kw):
            load_calls.append(kw)
            return {"REMOTE_USER": "root"}

        monkeypatch.setattr(app_module, "load_env_with_overrides", fake_load)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert len(load_calls) == 1
        assert str(load_calls[0]["global_env_path"]).endswith(".dsh/.env")


class TestLaunchToolSelection:
    """Tests for launch config-directory selection (--tool / auto-detect)."""

    def _make_config(self, tmp_path: Path, tool: str) -> Path:
        dirname = {"dsh": ".dsh", "qwen": ".qwen"}.get(tool, ".opencode")
        config = tmp_path / dirname
        config.mkdir()
        (config / "docker-compose.yaml").write_text(
            f"services:\n  {tool}:\n    container_name: ocf_repo\n"
        )
        (config / ".env").write_text(f"REMOTE_USER=root\nOCF_AGENT_TOOL={tool}\n")
        return config

    def _patch_launch_deps(self, monkeypatch, tmp_path: Path):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")
        captured: list = []

        def mock_run(*args, **kw):
            cmd = list(args[0]) if args else args[1].get("args", [])
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd[:2] == ["docker", "inspect"] and "--format" in cmd:
                result.stdout = ""  # no container
            elif cmd[:2] == ["docker", "compose"] and "run" in cmd:
                captured.append(cmd)
                result.returncode = 0
            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)
        return app_module, captured

    def _invoke(self, app_module, args: list):
        from typer.testing import CliRunner

        return CliRunner().invoke(app_module.app, args)

    def test_tool_flag_wins_over_auto_detect(self, tmp_path: Path, monkeypatch):
        """--tool qwen selects .qwen/ even when .opencode/ is also valid."""
        self._make_config(tmp_path, "opencode")
        self._make_config(tmp_path, "qwen")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--tool", "qwen"])

        assert result.exit_code == 0
        assert "Using qwen config at .qwen/" in result.output
        assert captured[0][-1] == "qwen"

    def test_auto_selects_single_valid_config(self, tmp_path: Path, monkeypatch):
        """With only .opencode/ valid, launch auto-selects it without --tool."""
        self._make_config(tmp_path, "opencode")
        app_module, _ = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 0
        assert "Using opencode config at .opencode/" in result.output

    def test_multiple_valid_configs_non_interactive_error(
        self, tmp_path: Path, monkeypatch
    ):
        """Two valid configs without --tool exit 1 in non-interactive mode."""
        self._make_config(tmp_path, "opencode")
        self._make_config(tmp_path, "qwen")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 1
        assert "multiple framework config directories found" in result.output
        assert ".opencode, .qwen" in result.output
        assert "pass --tool (opencode | qwen | dsh)" in result.output
        assert captured == []

    def test_three_valid_configs_non_interactive_error(
        self, tmp_path: Path, monkeypatch
    ):
        """Three valid configs list every dir in tool-sorted order."""
        self._make_config(tmp_path, "opencode")
        self._make_config(tmp_path, "qwen")
        self._make_config(tmp_path, "dsh")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 1
        assert ".dsh, .opencode, .qwen" in result.output
        assert "pass --tool (opencode | qwen | dsh)" in result.output
        assert captured == []

    def test_tool_flag_with_missing_config_errors(self, tmp_path: Path, monkeypatch):
        """--tool qwen without .qwen/ exits 1 with an init remediation."""
        self._make_config(tmp_path, "opencode")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch", "--tool", "qwen"])

        assert result.exit_code == 1
        assert "no .qwen/ framework config directory" in result.output
        assert "init --tool qwen" in result.output
        assert captured == []

    def test_mismatched_env_tool_never_launched(self, tmp_path: Path, monkeypatch):
        """.opencode/.env naming another tool blocks launch with re-init remediation."""
        self._make_config(tmp_path, "opencode")
        (tmp_path / ".opencode" / ".env").write_text(
            "REMOTE_USER=root\nOCF_AGENT_TOOL=qwen\n"
        )
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(app_module, ["launch"])

        assert result.exit_code == 1
        assert "OCF_AGENT_TOOL='qwen'" in result.output
        assert ".opencode/ is the opencode config directory" in result.output
        assert "init --force --tool opencode" in result.output
        assert captured == []

    def test_env_override_conflicting_with_tool_flag_warns(
        self, tmp_path: Path, monkeypatch
    ):
        """-e OCF_AGENT_TOOL conflicting with --tool launches but warns."""
        self._make_config(tmp_path, "opencode")
        app_module, captured = self._patch_launch_deps(monkeypatch, tmp_path)

        result = self._invoke(
            app_module, ["launch", "--tool", "opencode", "-e", "OCF_AGENT_TOOL=qwen"]
        )

        assert result.exit_code == 0
        assert "Using opencode config at .opencode/" in result.output
        assert "Warning: OCF_AGENT_TOOL='qwen'" in result.output


class _FakeProcess:
    """Minimal subprocess.Popen stand-in for devcontainer commands."""

    def __init__(self, lines, returncode=0):
        self.stdout = lines
        self.returncode = returncode

    def wait(self):
        return self.returncode


class TestPerToolImageTag:
    """Tests for per-tool image tag construction."""

    @pytest.mark.parametrize("tool", ["opencode", "qwen", "dsh"])
    def test_tag_format(self, tool):
        assert _per_tool_image_tag("myrepo", tool) == f"ocf-myrepo-{tool}:latest"

    def test_tags_differ_per_tool(self):
        assert _per_tool_image_tag("myrepo", "opencode") != _per_tool_image_tag(
            "myrepo", "qwen"
        )

    @pytest.mark.parametrize(
        "raw,slug",
        [
            ("myrepo", "myrepo"),
            ("My.Repo_1", "my.repo_1"),
            ("My Repo!", "my-repo"),
            ("-leading_trailing-", "leading_trailing"),
            ("...", "repo"),
        ],
    )
    def test_slugification(self, raw, slug):
        assert _per_tool_image_tag(raw, "opencode") == f"ocf-{slug}-opencode:latest"


class TestParseImageNameFromBuildJson:
    """Tests for imageName parsing from devcontainer build output."""

    def test_parses_list_image_name(self):
        output = '{"outcome":"success","imageName":["ocf-x-opencode:latest"]}\n'
        assert _parse_image_name_from_build_json(output) == "ocf-x-opencode:latest"

    def test_parses_string_image_name(self):
        output = '{"outcome":"success","imageName":"vsc-x"}\n'
        assert _parse_image_name_from_build_json(output) == "vsc-x"

    def test_ignores_failure_outcome_and_garbage(self):
        output = 'some log line\n{"outcome":"error","imageName":["x"]}\n'
        assert _parse_image_name_from_build_json(output) is None

    def test_ignores_missing_image_name(self):
        output = '{"outcome":"success"}\n'
        assert _parse_image_name_from_build_json(output) is None


class TestBuildImageTwoStep:
    """Tests for the up → build --image-name flow in _build_image."""

    def _patch_subprocess(
        self,
        monkeypatch,
        tmp_path: Path,
        tool: str = "opencode",
        old_id=None,
        new_id="sha256:new",
        build_rc=0,
    ):
        """Fake Popen (devcontainer) and run (docker) for _build_image."""
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")

        commands: list = []
        rmi_calls: list = []
        expected_tag = _per_tool_image_tag(tmp_path.name, tool)

        def fake_popen(cmd, **kw):
            commands.append(list(cmd))
            if "up" in cmd:
                lines = ['{"outcome":"success","containerId":"c1"}\n']
            else:
                lines = [f'{{"outcome":"success","imageName":["{expected_tag}"]}}\n']
            return _FakeProcess(lines, returncode=build_rc if "build" in cmd else 0)

        def fake_run(cmd, **kw):
            cmd = list(cmd)
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            if cmd[:2] == ["docker", "inspect"] and "--format={{.Config.Image}}" in cmd:
                result.stdout = "vsc-old-image\n"
            elif cmd[:2] == ["docker", "images"] and "--filter" in cmd:
                result.stdout = f"{old_id}\n" if old_id else ""
            elif cmd[:3] == ["docker", "image", "inspect"] and "{{.Id}}" in cmd:
                result.stdout = f"{new_id}\n"
            elif cmd[:2] == ["docker", "rmi"]:
                rmi_calls.append(cmd)
            return result

        monkeypatch.setattr(app_module.subprocess, "Popen", fake_popen)
        monkeypatch.setattr(app_module.subprocess, "run", fake_run)
        return app_module, commands, rmi_calls, expected_tag

    def _make_config(self, tmp_path: Path, tool: str) -> Path:
        config_dir = tmp_path / ("." + tool)
        config_dir.mkdir()
        (config_dir / "devcontainer.json").write_text("{}")
        return config_dir

    def test_up_then_build_with_per_tool_tag(self, tmp_path: Path, monkeypatch):
        """_build_image runs `up` first, then `build` with the per-tool tag."""
        tool = "opencode"
        config_dir = self._make_config(tmp_path, tool)
        app_module, commands, _, expected_tag = self._patch_subprocess(
            monkeypatch, tmp_path, tool=tool
        )

        tag = _build_image(config_dir, tmp_path, {}, tool)

        assert commands[0][:2] == ["devcontainer", "up"]
        assert commands[1][:2] == ["devcontainer", "build"]
        assert "--image-name" in commands[1]
        assert commands[1][commands[1].index("--image-name") + 1] == expected_tag
        assert tag == expected_tag

    @pytest.mark.parametrize("tool", ["opencode", "qwen", "dsh"])
    def test_tag_is_per_tool(self, tmp_path: Path, monkeypatch, tool):
        """The applied tag carries the tool name."""
        config_dir = self._make_config(tmp_path, tool)
        self._patch_subprocess(monkeypatch, tmp_path, tool=tool)

        tag = _build_image(config_dir, tmp_path, {}, tool)

        assert tag == f"ocf-{tmp_path.name}-{tool}:latest"

    def test_previous_image_removed_when_changed(self, tmp_path: Path, monkeypatch):
        """A previous image behind the tag is removed after the tag moves."""
        config_dir = self._make_config(tmp_path, "opencode")
        _, _, rmi_calls, _ = self._patch_subprocess(
            monkeypatch, tmp_path, old_id="sha256:old", new_id="sha256:new"
        )

        _build_image(config_dir, tmp_path, {}, "opencode")

        assert rmi_calls == [["docker", "rmi", "sha256:old"]]

    def test_same_image_not_removed(self, tmp_path: Path, monkeypatch):
        """Cache replay producing the same image triggers no cleanup."""
        config_dir = self._make_config(tmp_path, "opencode")
        _, _, rmi_calls, _ = self._patch_subprocess(
            monkeypatch, tmp_path, old_id="sha256:same", new_id="sha256:same"
        )

        _build_image(config_dir, tmp_path, {}, "opencode")

        assert rmi_calls == []

    def test_first_build_no_cleanup(self, tmp_path: Path, monkeypatch):
        """No previous tag → nothing to clean up."""
        config_dir = self._make_config(tmp_path, "opencode")
        _, _, rmi_calls, _ = self._patch_subprocess(
            monkeypatch, tmp_path, old_id=None, new_id="sha256:new"
        )

        _build_image(config_dir, tmp_path, {}, "opencode")

        assert rmi_calls == []

    def test_tag_step_failure_exits(self, tmp_path: Path, monkeypatch):
        """A failing `devcontainer build` step exits with code 1."""
        config_dir = self._make_config(tmp_path, "opencode")
        self._patch_subprocess(monkeypatch, tmp_path, build_rc=1)

        with pytest.raises(typer.Exit) as exc_info:
            _build_image(config_dir, tmp_path, {}, "opencode")

        assert exc_info.value.exit_code == 1


class TestLaunchBuildImageToolArg:
    """launch passes the selected tool name to _build_image."""

    def test_build_image_receives_tool_name(self, tmp_path: Path, monkeypatch):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")

        opencode = tmp_path / ".opencode"
        opencode.mkdir()
        (opencode / "docker-compose.yaml").write_text(
            "services:\n  opencode:\n    container_name: ocf_repo\n"
        )
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")

        build_args: list = []

        def fake_build(config_dir, repo_root, subprocess_env, agent_tool):
            build_args.append(agent_tool)
            return "sha256:fake"

        def mock_run(*args, **kw):
            result = type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            return result

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: None)
        monkeypatch.setattr(app_module, "_build_image", fake_build)
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(tmp_path)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0
        assert build_args == ["opencode"]


class TestLaunchRepoRootComputation:
    """OCF_LOCAL_REPO_ROOT derives from OCF_LOCAL_PROJECTS_DIR + repo name."""

    @staticmethod
    def _setup_repo(tmp_path: Path, projects_dir: Path) -> Path:
        """Create a fake repo under projects_dir with a minimal harness."""
        repo_root = projects_dir / "myrepo"
        opencode = repo_root / ".opencode"
        opencode.mkdir(parents=True)
        (opencode / "docker-compose.yaml").write_text(
            "services:\n  opencode:\n    container_name: ocf_repo\n"
        )
        (opencode / ".env").write_text("REMOTE_USER=root\nOCF_AGENT_TOOL=opencode\n")
        return repo_root

    def _invoke_launch(self, monkeypatch, app_module, repo_root: Path, final_env):
        """Mock the launch pipeline and run CLI launch from repo_root."""
        captured: dict = {}

        def fake_build(config_dir, repo_root, subprocess_env, agent_tool):
            captured.update(subprocess_env)
            return "sha256:fake"

        def mock_run(*args, **kw):
            return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

        monkeypatch.setattr(
            app_module,
            "validate_runtime_context",
            lambda cwd, config_dirname, repo_root=None: (True, ""),
        )
        monkeypatch.setattr(
            app_module, "get_repo_root", lambda cwd: repo_root.resolve()
        )
        monkeypatch.setattr(
            app_module, "load_env_with_overrides", lambda **kw: dict(final_env)
        )
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: None)
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(app_module, "_build_image", fake_build)
        monkeypatch.setattr(app_module.subprocess, "run", mock_run)
        monkeypatch.chdir(repo_root)

        from typer.testing import CliRunner

        result = CliRunner().invoke(app_module.app, ["launch"])
        return result, captured

    def _app_module(self):
        import importlib

        return importlib.import_module("opencode_framework.cli.app")

    def test_projects_dir_setting_used(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        projects_dir = tmp_path / "projects"
        repo_root = self._setup_repo(tmp_path, projects_dir)

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {"OCF_LOCAL_PROJECTS_DIR": str(projects_dir)},
        )

        assert result.exit_code == 0
        assert env["OCF_LOCAL_REPO_ROOT"] == str(projects_dir / "myrepo")
        assert "Note:" not in result.output

    def test_unset_falls_back_to_repo_parent_with_note(
        self, tmp_path: Path, monkeypatch
    ):
        app_module = self._app_module()
        repo_root = self._setup_repo(tmp_path, tmp_path)

        result, env = self._invoke_launch(monkeypatch, app_module, repo_root, {})

        assert result.exit_code == 0
        assert env["OCF_LOCAL_REPO_ROOT"] == str(repo_root)
        assert "OCF_LOCAL_PROJECTS_DIR" in result.output
        assert "Note:" in result.output

    def test_mismatched_projects_dir_hard_error(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        repo_root = self._setup_repo(tmp_path, tmp_path)
        elsewhere = tmp_path / "elsewhere"

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {"OCF_LOCAL_PROJECTS_DIR": str(elsewhere)},
        )

        assert result.exit_code == 1
        assert "OCF_LOCAL_PROJECTS_DIR mismatch" in result.output
        assert "launch -e OCF_LOCAL_PROJECTS_DIR" in result.output
        assert "OCF_LOCAL_REPO_ROOT" not in env

    def test_tilde_in_projects_dir_expanded(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        repo_root = self._setup_repo(home / "code-projects", home / "code-projects")

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {"OCF_LOCAL_PROJECTS_DIR": "~/code-projects"},
        )

        assert result.exit_code == 0
        assert env["OCF_LOCAL_REPO_ROOT"] == str(home / "code-projects" / "myrepo")

    def test_direct_repo_root_env_wins(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        projects_dir = tmp_path / "projects"
        repo_root = self._setup_repo(tmp_path, projects_dir)

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {
                "OCF_LOCAL_REPO_ROOT": str(repo_root),
                "OCF_LOCAL_PROJECTS_DIR": str(projects_dir),
            },
        )

        assert result.exit_code == 0
        assert env["OCF_LOCAL_REPO_ROOT"] == str(repo_root)
        assert "Note:" not in result.output

    def test_direct_repo_root_tilde_expanded(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        home = tmp_path / "home"
        monkeypatch.setenv("HOME", str(home))
        repo_root = self._setup_repo(home / "code-projects", home / "code-projects")

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {"OCF_LOCAL_REPO_ROOT": "~/code-projects/myrepo"},
        )

        assert result.exit_code == 0
        assert env["OCF_LOCAL_REPO_ROOT"] == str(home / "code-projects" / "myrepo")

    def test_direct_repo_root_mismatch_hard_error(self, tmp_path: Path, monkeypatch):
        app_module = self._app_module()
        repo_root = self._setup_repo(tmp_path, tmp_path)

        result, env = self._invoke_launch(
            monkeypatch,
            app_module,
            repo_root,
            {"OCF_LOCAL_REPO_ROOT": str(tmp_path / "elsewhere" / "myrepo")},
        )

        assert result.exit_code == 1
        assert "OCF_LOCAL_REPO_ROOT mismatch" in result.output
        assert "launch -e OCF_LOCAL_REPO_ROOT" in result.output
        assert "OCF_LOCAL_REPO_ROOT" not in env
