"""Tests for .opencode/ directory generation."""

import json
from pathlib import Path

import pytest

from opencode_framework.generator import (
    generate_opencode_directory,
    _generate_extended_devcontainer,
    _generate_scratch_devcontainer,
    _add_optional_features,
    _generate_env_file,
    _generate_readme,
    _get_launch_commands,
    GenerationContext,
)
from opencode_framework.wizard import WizardResult
from opencode_framework.devcontainer import DevcontainerInfo
from opencode_framework.config import GlobalSettings


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

        generate_opencode_directory(repo_root, wizard_result)

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

        generate_opencode_directory(repo_root, wizard_result)

        dc_content = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "name" in dc_content
        assert "features" in dc_content
        assert "mounts" in dc_content


class TestAddOptionalFeatures:
    """Tests for optional feature addition."""

    def test_docker_feature(self):
        """Docker feature should add DinD feature."""
        features = {}
        _add_optional_features(features, ["docker"], "none")
        assert "ghcr.io/devcontainers/features/docker-in-docker:2" in features

    def test_python_feature(self):
        """Python feature should add Python feature."""
        features = {}
        _add_optional_features(features, ["python"], "none")
        assert "ghcr.io/devcontainers/features/python:1" in features

    def test_nodejs_feature(self):
        """Node.js feature should add Node feature."""
        features = {}
        _add_optional_features(features, ["nodejs"], "none")
        assert "ghcr.io/devcontainers/features/node:1" in features

    def test_java_feature(self):
        """Java feature should add Java feature."""
        features = {}
        _add_optional_features(features, ["java"], "none")
        assert "ghcr.io/devcontainers/features/java:1" in features

    def test_vi_editor_choice(self):
        """vi editor choice should add vim to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        _add_optional_features(features, [], "vi")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "vim" in common_utils["installPackages"]

    def test_nano_editor_choice(self):
        """nano editor choice should add nano to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        _add_optional_features(features, [], "nano")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "nano" in common_utils["installPackages"]

    def test_none_editor_choice(self):
        """none editor choice should not add any editor packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        _add_optional_features(features, [], "none")
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" not in common_utils


class TestExtendedDevcontainer:
    """Tests for extended devcontainer generation."""

    def _make_global_settings(self, **kwargs):
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

    def test_extends_existing_image(self, tmp_path: Path):
        """Extended devcontainer should inherit image from existing."""
        existing = {"image": "custom-image:latest"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert result["image"] == "custom-image:latest"

    def test_extends_existing_features(self, tmp_path: Path):
        """Extended devcontainer should merge features."""
        existing = {
            "image": "ubuntu:22.04",
            "features": {
                "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
            },
        }
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=["nodejs"],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "ghcr.io/devcontainers/features/python:1" in result["features"]
        assert "ghcr.io/devcontainers/features/node:1" in result["features"]

    def test_no_docker_context_in_remote_env(self, tmp_path: Path):
        """Extended devcontainer should NOT set DOCKER_CONTEXT in remoteEnv."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=["docker"],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "DOCKER_CONTEXT" not in result.get("remoteEnv", {})


class TestTemplateMounts:
    """Tests for template-based mounts."""

    def _make_global_settings(self, **kwargs):
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

    def test_scratch_has_runtime_data_mounts(self, tmp_path: Path):
        """Scratch devcontainer should have runtime_data mounts."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        cache_mounts = [m for m in mounts if "runtime_data/.cache" in m.get("source", "")]
        assert len(cache_mounts) == 1
        
        data_mounts = [m for m in mounts if "runtime_data/.local/share" in m.get("source", "")]
        assert len(data_mounts) == 1

    def test_scratch_has_global_config_mount(self, tmp_path: Path):
        """Scratch devcontainer should mount global config via template."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_config_found=True,
                global_config_path="/home/user/.config/opencode",
            ),
        )

        result = _generate_scratch_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        config_mounts = [m for m in mounts if "OCF_LOCAL_GLOBAL_CONFIG_PATH" in m.get("source", "")]
        assert len(config_mounts) == 1
        assert config_mounts[0]["readOnly"] is True


class TestOpenCodeFeature:
    """Tests for OpenCode feature inclusion."""

    def _make_global_settings(self, **kwargs):
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

    def test_opencode_feature_in_scratch(self, tmp_path: Path):
        """Scratch devcontainer should include OpenCode feature."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "ghcr.io/stu-bell/devcontainer-features/open-code:0" in result["features"]
        
        feature = result["features"]["ghcr.io/stu-bell/devcontainer-features/open-code:0"]
        assert "open_code_version" in feature
        assert "OPENCODE_VERSION" in feature["open_code_version"]

    def test_opencode_feature_in_extend(self, tmp_path: Path):
        """Extended devcontainer should include OpenCode feature."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "ghcr.io/stu-bell/devcontainer-features/open-code:0" in result["features"]


class TestRemoteUser:
    """Tests for remoteUser configuration."""

    def _make_global_settings(self, **kwargs):
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

    def test_remote_user_uses_env_var_in_scratch(self, tmp_path: Path):
        """Scratch devcontainer should use REMOTE_USER env var."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "REMOTE_USER" in result["remoteUser"]

    def test_remote_user_preserves_existing_in_extend(self, tmp_path: Path):
        """Extended devcontainer should preserve existing remoteUser."""
        existing = {
            "image": "ubuntu:22.04",
            "remoteUser": "custom-user",
        }
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert result["remoteUser"] == "custom-user"


class TestEnvFileGeneration:
    """Tests for .env file generation."""

    def _make_global_settings(self, **kwargs):
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

    def test_env_contains_docker_context(self, tmp_path: Path):
        """Generated .env should contain DOCKER_CONTEXT."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "DOCKER_CONTEXT=rootless" in env_content

    def test_env_contains_remote_user(self, tmp_path: Path):
        """Generated .env should contain REMOTE_USER."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "REMOTE_USER=root" in env_content

    def test_env_contains_xdg_vars(self, tmp_path: Path):
        """Generated .env should contain XDG variables."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "XDG_CONFIG_HOME" in env_content
        assert "XDG_DATA_HOME" in env_content
        assert "XDG_STATE_HOME" in env_content
        assert "XDG_CACHE_HOME" in env_content

    def test_env_contains_model_vars(self, tmp_path: Path):
        """Generated .env should contain model configuration vars."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_MAIN_MODEL" in env_content
        assert "OCF_BUILD_MODEL" in env_content
        assert "OCF_SMALL_MODEL" in env_content


class TestPostAttachCommand:
    """Tests for postAttachCommand configuration."""

    def _make_global_settings(self, **kwargs):
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

    def test_post_attach_command_opencode(self, tmp_path: Path):
        """Scratch devcontainer should have postAttachCommand with opencode."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "postAttachCommand" in result
        assert result["postAttachCommand"] == "opencode --continue"

    def test_no_post_start_command(self, tmp_path: Path):
        """Scratch devcontainer should NOT have postStartCommand."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "postStartCommand" not in result

    def test_post_attach_command_in_extend(self, tmp_path: Path):
        """Extended devcontainer should have postAttachCommand."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "postAttachCommand" in result
        assert result["postAttachCommand"] == "opencode --continue"


class TestLaunchCommands:
    """Tests for host-side launch command generation."""

    def test_launch_command_sources_env(self):
        """Launch command should source .env file."""
        commands = _get_launch_commands()
        assert "source .opencode/.env" in commands["launch"]
        assert "devcontainer up" in commands["launch"]

    def test_debug_command_sources_env(self):
        """Debug command should source .env file."""
        commands = _get_launch_commands()
        assert "source .opencode/.env" in commands["debug"]
        assert "opencode debug config" in commands["debug"]

    def test_shell_command_sources_env(self):
        """Shell command should source .env file."""
        commands = _get_launch_commands()
        assert "source .opencode/.env" in commands["shell"]
        assert "devcontainer exec" in commands["shell"]

    def test_no_docker_context_in_commands(self):
        """Commands should NOT contain DOCKER_CONTEXT inline."""
        commands = _get_launch_commands()
        assert "DOCKER_CONTEXT=rootless" not in commands["launch"]
        assert "DOCKER_CONTEXT=rootless" not in commands["debug"]
        assert "DOCKER_CONTEXT=rootless" not in commands["shell"]


class TestReadmeLaunchCommand:
    """Tests for README launch command content."""

    def _make_global_settings(self, **kwargs):
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

    def test_readme_sources_env_in_launch(self, tmp_path: Path):
        """README should show sourced-env launch command."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_readme(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "source .opencode/.env" in readme_content
        assert "devcontainer up" in readme_content

    def test_readme_has_debug_command(self, tmp_path: Path):
        """README should show debug command."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_readme(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "opencode debug config" in readme_content

    def test_readme_has_shell_command(self, tmp_path: Path):
        """README should show shell command."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_readme(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "### Shell" in readme_content

    def test_readme_describes_attach_startup(self, tmp_path: Path):
        """README should describe postAttachCommand startup."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_readme(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "postAttachCommand" in readme_content
