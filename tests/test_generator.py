"""Tests for .opencode/ directory generation."""

import json
from pathlib import Path

import pytest

from opencode_framework.generator import (
    generate_opencode_directory,
    _generate_extended_devcontainer,
    _generate_scratch_devcontainer,
    _add_optional_features,
    _build_mounts,
    _generate_env_file,
    _generate_readme,
    _get_launch_command,
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


class TestBuildMounts:
    """Tests for mount building."""

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

    def test_no_local_opencode_mounts(self, tmp_path: Path):
        """Should not mount local .opencode files - they're accessible via workspaceMount."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        mounts = _build_mounts(ctx)
        local_opencode_mounts = [m for m in mounts if "${localWorkspaceFolder}/.opencode" in m.get("source", "")]
        assert len(local_opencode_mounts) == 0

    def test_global_config_mount(self, tmp_path: Path):
        """Should mount global config read-only."""
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

        mounts = _build_mounts(ctx)
        config_mounts = [m for m in mounts if "opencode" in m["target"] and ".config" in m["target"]]
        assert len(config_mounts) == 1
        assert config_mounts[0]["readOnly"] is True

    def test_global_auth_mount(self, tmp_path: Path):
        """Should mount global auth.json read-only."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_auth_found=True,
                global_auth_path="/home/user/.local/share/opencode/auth.json",
            ),
        )

        mounts = _build_mounts(ctx)
        auth_mounts = [m for m in mounts if "auth.json" in m["target"]]
        assert len(auth_mounts) == 1
        assert auth_mounts[0]["readOnly"] is True

    def test_framework_config_mount(self, tmp_path: Path):
        """Should mount framework config read-only."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                framework_config_path="/path/to/framework-config",
            ),
        )

        mounts = _build_mounts(ctx)
        framework_mounts = [m for m in mounts if "ocframework" in m["target"]]
        assert len(framework_mounts) == 1
        assert framework_mounts[0]["readOnly"] is True
        assert framework_mounts[0]["target"] == "/opt/ocframework/config"


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
        """Scratch devcontainer should use env var for remoteUser."""
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
        assert "OCF_REMOTE_USER" in result["remoteUser"]
        assert "vscode" in result["remoteUser"]

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

    def test_remote_user_uses_env_var_in_extend_without_existing(self, tmp_path: Path):
        """Extended devcontainer without remoteUser should use env var."""
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
        assert "OCF_REMOTE_USER" in result["remoteUser"]
        assert "vscode" in result["remoteUser"]


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

    def test_editor_omitted_when_none(self, tmp_path: Path):
        """EDITOR should not be in .env when editor_choice is none."""
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
        assert "EDITOR=" not in env_content

    def test_editor_present_when_vi(self, tmp_path: Path):
        """EDITOR should be in .env when editor_choice is vi."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="vi",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "EDITOR=vi" in env_content

    def test_editor_present_when_nano(self, tmp_path: Path):
        """EDITOR should be in .env when editor_choice is nano."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="nano",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "EDITOR=nano" in env_content

    def test_env_is_override_only(self, tmp_path: Path):
        """Values should be commented examples, not active defaults."""
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
        assert "# OCF_REMOTE_USER=vscode" in env_content
        assert "# OCF_BASE_IMAGE=" in env_content

    def test_feature_vars_only_for_selected(self, tmp_path: Path):
        """Feature version vars should only appear for selected features."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=["python", "docker"],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_PYTHON_VERSION" in env_content
        assert "OCF_DOCKER_FEATURE_VERSION" in env_content
        assert "OCF_NODE_VERSION" not in env_content
        assert "OCF_JAVA_VERSION" not in env_content

    def test_no_feature_vars_when_none_selected(self, tmp_path: Path):
        """No feature version vars when no features selected."""
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
        assert "OCF_PYTHON_VERSION" not in env_content
        assert "OCF_NODE_VERSION" not in env_content
        assert "OCF_JAVA_VERSION" not in env_content
        assert "OCF_DOCKER_FEATURE_VERSION" not in env_content


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
        assert "opencode" in result["postAttachCommand"]

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

    def test_no_docker_context_in_attach_command(self, tmp_path: Path):
        """postAttachCommand should NOT contain DOCKER_CONTEXT."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=["docker"],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "DOCKER_CONTEXT" not in result["postAttachCommand"]

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
        assert "opencode" in result["postAttachCommand"]


class TestLaunchCommand:
    """Tests for host-side launch command generation."""

    def test_launch_command_without_docker(self):
        """Launch command should be plain when Docker not selected."""
        cmd = _get_launch_command([])
        assert cmd == "devcontainer up --config .opencode/devcontainer.json --workspace-folder ."

    def test_launch_command_with_docker(self):
        """Launch command should include DOCKER_CONTEXT when Docker selected."""
        cmd = _get_launch_command(["docker"])
        assert cmd.startswith("DOCKER_CONTEXT=rootless")
        assert "devcontainer up" in cmd

    def test_launch_command_with_docker_and_other_features(self):
        """Launch command should include DOCKER_CONTEXT when Docker among features."""
        cmd = _get_launch_command(["python", "docker", "nodejs"])
        assert cmd.startswith("DOCKER_CONTEXT=rootless")


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

    def test_readme_plain_launch_without_docker(self, tmp_path: Path):
        """README should show plain launch command when Docker not selected."""
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
        assert "devcontainer up --config .opencode/devcontainer.json --workspace-folder ." in readme_content
        assert "DOCKER_CONTEXT" not in readme_content

    def test_readme_docker_context_launch_with_docker(self, tmp_path: Path):
        """README should show DOCKER_CONTEXT launch when Docker selected."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=["docker"],
            editor_choice="none",
            global_settings=self._make_global_settings(),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_readme(ctx)
        
        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "DOCKER_CONTEXT=rootless devcontainer up" in readme_content

    def test_readme_describes_attach_startup(self, tmp_path: Path):
        """README should describe postAttachCommand startup, not container launch."""
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
        assert "container launches" not in readme_content
