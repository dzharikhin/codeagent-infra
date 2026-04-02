"""Tests for .opencode/ directory generation."""

import json
from pathlib import Path

import pytest

from opencode_framework.generators import GenerationOrchestrator, GenerationContext
from opencode_framework.generators.devcontainer import DevcontainerGenerator
from opencode_framework.generators.config_files import ConfigFilesGenerator
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.wizard import WizardResult
from opencode_framework.config import GlobalSettings


def _make_global_settings(**kwargs):
    """Create GlobalSettings with defaults."""
    defaults = {
        "framework_repo_path": None,
        "framework_config_path": None,
        "global_config_found": False,
        "global_config_path": None,
        "global_auth_found": False,
        "global_auth_path": None,
    }
    defaults.update(kwargs)
    return GlobalSettings(**defaults)


def _make_generation_context(tmp_path: Path, **kwargs):
    """Create GenerationContext with defaults."""
    defaults = {
        "repo_root": tmp_path,
        "opencode_dir": tmp_path / ".opencode",
        "branch_name": "codeagent-test",
        "devcontainer_strategy": "from_scratch",
        "optional_features": [],
        "editor_choice": "none",
        "global_settings": _make_global_settings(),
        "existing_devcontainer": None,
    }
    defaults.update(kwargs)
    return GenerationContext(**defaults)


class TestGenerateOpencodeDirectory:
    """Tests for .opencode/ generation."""

    def test_creates_required_files(self, tmp_path: Path):
        """Should create all required files in .opencode/."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        assert (opencode_dir / "devcontainer.json").exists()
        assert (opencode_dir / ".env").exists()
        assert (opencode_dir / "README.md").exists()
        assert (opencode_dir / ".gitignore").exists()
        assert (opencode_dir / "runtime_data").is_dir()

    def test_devcontainer_json_valid(self, tmp_path: Path):
        """Generated devcontainer.json should be valid JSON."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        dc_content = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "name" in dc_content
        assert "features" in dc_content


class TestAddOptionalFeatures:
    """Tests for optional feature addition."""

    def test_docker_feature(self):
        """Docker feature should add DinD feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["docker"], "none")
        assert "ghcr.io/devcontainers/features/docker-in-docker:2" in features

    def test_python_feature(self):
        """Python feature should add Python feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["python"], "none")
        assert "ghcr.io/devcontainers/features/python:1" in features

    def test_nodejs_feature(self):
        """Node.js feature should add Node feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["nodejs"], "none")
        assert "ghcr.io/devcontainers/features/node:1" in features

    def test_java_feature(self):
        """Java feature should add Java feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["java"], "none")
        assert "ghcr.io/devcontainers/features/java:1" in features

    def test_vi_editor_choice(self):
        """vi editor choice should add vim to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        DevcontainerGenerator._add_optional_features(features, [], "vi")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "vim" in common_utils["installPackages"]

    def test_nano_editor_choice(self):
        """nano editor choice should add nano to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        DevcontainerGenerator._add_optional_features(features, [], "nano")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "nano" in common_utils["installPackages"]

    def test_none_editor_choice(self):
        """none editor choice should not add any editor packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        DevcontainerGenerator._add_optional_features(features, [], "none")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" not in common_utils


class TestDevcontainerGenerator:
    """Tests for devcontainer generator."""

    def test_scratch_has_features(self, tmp_path: Path):
        """Scratch devcontainer should have features."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert "features" in dc_content
        assert "ghcr.io/devcontainers/features/git:1" in dc_content["features"]

    def test_extended_preserves_existing_image(self, tmp_path: Path):
        """Extended devcontainer should inherit image from existing."""
        (tmp_path / ".opencode").mkdir()
        existing = {"image": "custom-image:latest"}
        ctx = _make_generation_context(
            tmp_path,
            devcontainer_strategy="extend",
            existing_devcontainer=existing
        )
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert dc_content["image"] == "custom-image:latest"

    def test_extended_merges_features(self, tmp_path: Path):
        """Extended devcontainer should merge features."""
        (tmp_path / ".opencode").mkdir()
        existing = {
            "image": "ubuntu:22.04",
            "features": {
                "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
            },
        }
        ctx = _make_generation_context(
            tmp_path,
            devcontainer_strategy="extend",
            optional_features=["nodejs"],
            existing_devcontainer=existing
        )
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert "ghcr.io/devcontainers/features/python:1" in dc_content["features"]
        assert "ghcr.io/devcontainers/features/node:1" in dc_content["features"]

    def test_remote_user_uses_env_var(self, tmp_path: Path):
        """Devcontainer should use REMOTE_USER env var."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert "REMOTE_USER" in dc_content.get("remoteUser", "")


class TestOpenCodeFeature:
    """Tests for OpenCode feature inclusion."""

    def test_opencode_feature_in_scratch(self, tmp_path: Path):
        """Scratch devcontainer should include OpenCode feature."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert "ghcr.io/stu-bell/devcontainer-features/open-code:0" in dc_content["features"]
        
        feature = dc_content["features"]["ghcr.io/stu-bell/devcontainer-features/open-code:0"]
        assert "open_code_version" in feature
        assert "OPENCODE_VERSION" in feature["open_code_version"]

    def test_opencode_feature_in_extend(self, tmp_path: Path):
        """Extended devcontainer should include OpenCode feature."""
        (tmp_path / ".opencode").mkdir()
        existing = {"image": "ubuntu:22.04"}
        ctx = _make_generation_context(
            tmp_path,
            devcontainer_strategy="extend",
            existing_devcontainer=existing
        )
        
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        
        dc_content = json.loads((tmp_path / ".opencode" / "devcontainer.json").read_text())
        assert "ghcr.io/stu-bell/devcontainer-features/open-code:0" in dc_content["features"]


class TestEnvFileGeneration:
    """Tests for .env file generation."""

    def test_env_contains_remote_user(self, tmp_path: Path):
        """Generated .env should contain REMOTE_USER."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = ConfigFilesGenerator()
        gen.generate(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "REMOTE_USER=root" in env_content

    def test_env_contains_xdg_vars(self, tmp_path: Path):
        """Generated .env should contain XDG variables."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = ConfigFilesGenerator()
        gen.generate(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "XDG_CONFIG_HOME" in env_content
        assert "XDG_DATA_HOME" in env_content
        assert "XDG_STATE_HOME" in env_content
        assert "XDG_CACHE_HOME" in env_content

    def test_env_contains_model_vars(self, tmp_path: Path):
        """Generated .env should contain model configuration vars."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = ConfigFilesGenerator()
        gen.generate(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_MAIN_MODEL" in env_content
        assert "OCF_BUILD_MODEL" in env_content
        assert "OCF_SMALL_MODEL" in env_content

    def test_env_contains_editor_when_selected(self, tmp_path: Path):
        """Generated .env should contain EDITOR when editor_choice is not 'none'."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path, editor_choice="vi")
        
        gen = ConfigFilesGenerator()
        gen.generate(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "EDITOR=vi" in env_content

    def test_env_omits_editor_when_none(self, tmp_path: Path):
        """Generated .env should not contain EDITOR when editor_choice is 'none'."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path, editor_choice="none")
        
        gen = ConfigFilesGenerator()
        gen.generate(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "EDITOR=" not in env_content


class TestLaunchCommands:
    """Tests for host-side launch command generation."""

    def test_launch_command_is_cli(self):
        """Launch command should use ocframework CLI."""
        commands = DocumentationGenerator._get_launch_commands()
        assert commands["launch"] == "ocframework launch"

    def test_debug_command_is_cli(self):
        """Debug command should use ocframework exec CLI."""
        commands = DocumentationGenerator._get_launch_commands()
        assert commands["debug"] == "ocframework exec -- opencode debug config"

    def test_shell_command_is_cli(self):
        """Shell command should use ocframework exec CLI."""
        commands = DocumentationGenerator._get_launch_commands()
        assert commands["shell"] == "ocframework exec -- bash"


class TestReadmeLaunchCommand:
    """Tests for README launch command content."""

    def test_readme_shows_cli_launch(self, tmp_path: Path):
        """README should show CLI launch command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DocumentationGenerator()
        gen.generate(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "ocframework launch" in readme_content

    def test_readme_has_debug_command(self, tmp_path: Path):
        """README should show debug command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DocumentationGenerator()
        gen.generate(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "opencode debug config" in readme_content

    def test_readme_has_shell_command(self, tmp_path: Path):
        """README should show shell command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DocumentationGenerator()
        gen.generate(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "### Shell" in readme_content


class TestRuntimeDataStructure:
    """Tests for runtime_data directory structure."""

    def test_creates_only_xdg_directories(self, tmp_path: Path):
        """Should only create XDG-backed directories."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        runtime_data = opencode_dir / "runtime_data"
        assert runtime_data.is_dir()
        
        assert (runtime_data / ".cache").is_dir()
        assert (runtime_data / ".local" / "share").is_dir()
        assert (runtime_data / ".local" / "state").is_dir()

    def test_no_unused_directories(self, tmp_path: Path):
        """Should not create unused directories."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        runtime_data = opencode_dir / "runtime_data"
        
        assert not (runtime_data / "logs").exists()
        assert not (runtime_data / "tools").exists()
        assert not (runtime_data / "temp").exists()

    def test_gitignore_ignores_runtime_data(self, tmp_path: Path):
        """gitignore should ignore runtime_data directory."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        gitignore_content = (opencode_dir / ".gitignore").read_text()
        
        assert "runtime_data/" in gitignore_content


class TestReadmeFrameworkUrl:
    """Tests for README framework URL."""

    def test_readme_has_framework_url(self, tmp_path: Path):
        """README should have framework docs URL."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)
        
        gen = DocumentationGenerator()
        gen.generate(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "https://github.com/dzharikhin/codeagent-infra" in readme_content
