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


class TestExecCommand:
    """Tests for exec command."""

    def test_exec_requires_git_repo(self, tmp_path: Path):
        """exec should fail outside a git repo."""
        result = subprocess.run(
            [sys.executable, "-m", "opencode_framework", "exec", "--", "echo", "test"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert "not inside a Git working tree" in result.stdout or "not inside a Git working tree" in result.stderr

    def test_exec_requires_double_dash(self, tmp_path: Path):
        """exec should fail when no command is provided."""
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
            [sys.executable, "-m", "opencode_framework", "exec"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert "No command specified" in result.stdout or "No command specified" in result.stderr

    def test_exec_requires_opencode_dir(self, tmp_path: Path):
        """exec should fail when .opencode doesn't exist."""
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
            [sys.executable, "-m", "opencode_framework", "exec", "--", "echo", "test"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
        assert ".opencode/" in result.stdout or ".opencode/" in result.stderr
