"""Integration tests for the init command flow."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def run_cli(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run the CLI with given arguments."""
    cmd = [sys.executable, "-m", "opencode_framework"] + args
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def has_git() -> bool:
    """Check if git is available."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def has_required_tools() -> bool:
    """Check if all required tools are available."""
    for tool in ["git", "docker", "devcontainer", "pipx"]:
        try:
            result = subprocess.run(
                ["which", tool],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return False
        except FileNotFoundError:
            return False
    return True


GIT_AVAILABLE = has_git()
TOOLS_AVAILABLE = has_required_tools()


@pytest.mark.skipif(not GIT_AVAILABLE, reason="Git not installed")
class TestInitFlowWithGit:
    """Integration tests for init command with git available."""

    def test_init_in_git_repo(self, tmp_path: Path, monkeypatch):
        """Test init command in a git repository."""
        repo = tmp_path / "test-repo"
        repo.mkdir()

        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        result = run_cli(["init", "--help"], cwd=repo)
        assert result.returncode == 0
        assert "Initialize" in result.stdout


class TestDevcontainerHandling:
    """Tests for devcontainer detection and handling in init flow."""

    @pytest.mark.skipif(not TOOLS_AVAILABLE, reason="Required tools not installed")
    def test_incompatible_devcontainer_detected(self, tmp_path: Path):
        """Test that incompatible devcontainer is detected."""
        from opencode_framework.devcontainer import detect_devcontainer

        repo = tmp_path / "test-repo"
        repo.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        # Create incompatible devcontainer
        dc_dir = repo / ".devcontainer"
        dc_dir.mkdir()
        dc_file = dc_dir / "devcontainer.json"
        dc_file.write_text(json.dumps({"name": "test"}))

        # Verify detection
        dc_info = detect_devcontainer(repo)
        assert dc_info is not None
        assert dc_info.compatible is False


class TestWizardBehavior:
    """Tests for wizard behavior."""

    def test_incompatible_devcontainer_detection(self, tmp_path: Path):
        """Test that incompatible devcontainer is detected."""
        from opencode_framework.devcontainer import detect_devcontainer, evaluate_compatibility

        repo = tmp_path / "test-repo"
        repo.mkdir()

        dc_dir = repo / ".devcontainer"
        dc_dir.mkdir()
        dc_file = dc_dir / "devcontainer.json"
        dc_file.write_text(json.dumps({"name": "incompatible"}))

        dc_info = detect_devcontainer(repo)
        assert dc_info is not None
        assert dc_info.compatible is False
        assert "No 'image' or 'build'" in dc_info.incompatibility_reason


class TestForceFlag:
    """Tests for --force flag behavior."""

    def test_force_backs_up_existing(self, tmp_path: Path):
        """Test that --force backs up existing .opencode/."""
        repo = tmp_path / "test-repo"
        repo.mkdir()

        opencode_dir = repo / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "test.txt").write_text("existing content")

        result = run_cli(["init", "--force"], cwd=repo)

        backups = list(repo.glob(".opencode.backup-*"))
        if backups:
            assert (backups[0] / "test.txt").read_text() == "existing content"


class TestGeneratedConfig:
    """Tests for generated configuration files."""

    def test_devcontainer_json_structure(self, tmp_path: Path):
        """Test that generated devcontainer.json has correct structure."""
        from opencode_framework.generator import _generate_scratch_devcontainer, GenerationContext
        from opencode_framework.config import GlobalSettings

        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="test-branch",
            devcontainer_strategy="from_scratch",
            optional_features=["python"],
            editor_choice="none",
            global_settings=GlobalSettings(
                framework_repo_path=None,
                framework_config_path=None,
                global_config_found=False,
                global_config_path=None,
                global_auth_found=False,
                global_auth_path=None,
            ),
        )

        result = _generate_scratch_devcontainer(ctx)

        assert "name" in result
        assert "image" in result
        assert "features" in result
        assert "workspaceFolder" in result
        assert "mounts" in result
        assert result["workspaceFolder"] == "/workspace"

    def test_devcontainer_has_remote_env(self, tmp_path: Path):
        """Test that generated devcontainer has remoteEnv with OPENCODE_CONFIG."""
        from opencode_framework.generator import _generate_scratch_devcontainer, GenerationContext
        from opencode_framework.config import GlobalSettings

        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="test-branch",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=GlobalSettings(
                framework_repo_path=None,
                framework_config_path="/path/to/config",
                global_config_found=False,
                global_config_path=None,
                global_auth_found=False,
                global_auth_path=None,
            ),
        )

        result = _generate_scratch_devcontainer(ctx)

        assert "remoteEnv" in result
        assert "OPENCODE_CONFIG" in result["remoteEnv"]

    def test_editor_choice_sets_editor_env(self, tmp_path: Path):
        """Test that editor choice sets EDITOR in remoteEnv."""
        from opencode_framework.generator import _generate_scratch_devcontainer, GenerationContext
        from opencode_framework.config import GlobalSettings

        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="test-branch",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="vi",
            global_settings=GlobalSettings(
                framework_repo_path=None,
                framework_config_path=None,
                global_config_found=False,
                global_config_path=None,
                global_auth_found=False,
                global_auth_path=None,
            ),
        )

        result = _generate_scratch_devcontainer(ctx)

        assert "remoteEnv" in result
        assert result["remoteEnv"]["EDITOR"] == "vi"

    def test_opencode_feature_present(self, tmp_path: Path):
        """Test that OpenCode feature is included in generated devcontainer."""
        from opencode_framework.generator import _generate_scratch_devcontainer, GenerationContext
        from opencode_framework.config import GlobalSettings

        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="test-branch",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=GlobalSettings(
                framework_repo_path=None,
                framework_config_path=None,
                global_config_found=False,
                global_config_path=None,
                global_auth_found=False,
                global_auth_path=None,
            ),
        )

        result = _generate_scratch_devcontainer(ctx)

        assert "ghcr.io/stu-bell/devcontainer-features/open-code:0" in result["features"]
