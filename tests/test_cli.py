"""Tests for CLI behavior."""

import subprocess
import sys
from pathlib import Path


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
            [sys.executable, "-m", "opencode_framework", "init"],
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
        assert "not inside a Git working tree" in result.stdout or "not inside a Git working tree" in result.stderr

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
        assert "not the repository root" in result.stdout or "not the repository root" in result.stderr

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
        assert ".opencode/" in result.stdout or ".opencode/" in result.stderr

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
        
        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "launch"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert "devcontainer.json" in result.stdout or "devcontainer.json" in result.stderr

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
        return opencode

    def _patch_launch_deps(self, monkeypatch, tmp_path: Path):
        import importlib

        app_module = importlib.import_module("opencode_framework.cli.app")

        monkeypatch.setattr(app_module, "validate_runtime_context", lambda cwd: (True, ""))
        monkeypatch.setattr(app_module, "get_repo_root", lambda cwd: tmp_path.resolve())
        monkeypatch.setattr(app_module, "load_env_with_overrides", lambda **kw: {})
        monkeypatch.setattr(app_module, "build_docker_env", lambda env, ctx: {})
        monkeypatch.setattr(app_module, "load_image_id", lambda d: None)
        monkeypatch.setattr(app_module, "_build_image", lambda *a, **kw: "sha256:fake")
        monkeypatch.setattr(app_module, "save_image_id", lambda *a, **kw: None)
        monkeypatch.setattr(
            app_module.subprocess, "run",
            lambda *a, **kw: type("R", (), {"returncode": 0})(),
        )
        return app_module

    def test_rebuild_invokes_update_features(self, tmp_path: Path, monkeypatch):
        """--rebuild must call update_features before building."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)

        calls = {}

        def fake_update(opencode_dir, repo_name):
            calls["args"] = (opencode_dir, repo_name)
            return False

        monkeypatch.setattr(app_module, "update_features", fake_update)

        from typer.testing import CliRunner
        result = CliRunner().invoke(app_module.app, ["launch", "--rebuild"])

        assert result.exit_code == 0
        assert "args" in calls
        assert calls["args"][0].name == ".opencode"
        assert calls["args"][1] == tmp_path.name

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
        monkeypatch.setattr(app_module, "update_features", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not be called")))

        from typer.testing import CliRunner
        result = CliRunner().invoke(app_module.app, ["launch"])

        assert result.exit_code == 0

    def test_launch_handles_keyboard_interrupt(self, tmp_path: Path, monkeypatch):
        """launch must clean up container on KeyboardInterrupt."""
        self._setup_repo(tmp_path)
        app_module = self._patch_launch_deps(monkeypatch, tmp_path)
        monkeypatch.setattr(app_module, "load_image_id", lambda d: "sha256:cached")

        # Track subprocess calls
        subprocess_calls = []

        def fake_run(*args, **kwargs):
            subprocess_calls.append(("run", args, kwargs))
            if "docker" in args[0]:
                # Simulate docker compose run being interrupted
                raise KeyboardInterrupt()
            return type("R", (), {"returncode": 0})()

        monkeypatch.setattr(app_module.subprocess, "run", fake_run)

        from typer.testing import CliRunner
        result = CliRunner().invoke(app_module.app, ["launch", "--serve", "--port", "33050", "--hostname", "0.0.0.0"])

        assert result.exit_code == 130  # Standard SIGINT exit code
        assert len(subprocess_calls) >= 2  # At least run and cleanup

        # Verify cleanup was called
        cleanup_cmds = [call for call in subprocess_calls if "rm -f" in str(call) or "down" in str(call)]
        assert len(cleanup_cmds) > 0, "Cleanup commands should have been called"

