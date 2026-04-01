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
    _merge_mounts,
    _extract_mount_target,
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
        
        cache_mounts = [m for m in mounts if "runtime_data/.cache" in str(m)]
        assert len(cache_mounts) == 1
        
        data_mounts = [m for m in mounts if "runtime_data/.local/share" in str(m)]
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
        
        config_mounts = [m for m in mounts if "OCF_LOCAL_GLOBAL_CONFIG_PATH" in str(m)]
        assert len(config_mounts) == 1
        assert "readonly" in str(config_mounts[0])

    def test_scratch_no_global_config_mount_when_missing(self, tmp_path: Path):
        """Scratch devcontainer should NOT mount global config when not found."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_config_found=False,
                global_config_path=None,
            ),
        )

        result = _generate_scratch_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        config_mounts = [m for m in mounts if "OCF_LOCAL_GLOBAL_CONFIG_PATH" in str(m)]
        assert len(config_mounts) == 0

    def test_extended_no_global_config_mount_when_missing(self, tmp_path: Path):
        """Extended devcontainer should NOT mount global config when not found."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_config_found=False,
                global_config_path=None,
            ),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        config_mounts = [m for m in mounts if "OCF_LOCAL_GLOBAL_PATH" in str(m) or "XDG_CONFIG_HOME}/opencode" in str(m)]
        assert len(config_mounts) == 0

    def test_global_auth_mount_is_readonly(self, tmp_path: Path):
        """Global auth.json mount should be readonly."""
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

        result = _generate_scratch_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        auth_mounts = [m for m in mounts if "OCF_LOCAL_GLOBAL_AUTH_PATH" in str(m)]
        assert len(auth_mounts) == 1
        assert "readonly" in str(auth_mounts[0])

    def test_framework_config_mount_is_readonly(self, tmp_path: Path):
        """Framework config mount should be readonly."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                framework_repo_path="/path/to/framework",
            ),
        )

        result = _generate_scratch_devcontainer(ctx)
        mounts = result.get("mounts", [])
        
        framework_mounts = [m for m in mounts if "OCF_LOCAL_FRAMEWORK_PATH" in str(m)]
        assert len(framework_mounts) == 1
        assert "readonly" in str(framework_mounts[0])


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


class TestEditorRemoteEnv:
    """Tests for EDITOR remoteEnv configuration."""

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

    def test_editor_uses_local_env_in_scratch(self, tmp_path: Path):
        """Scratch devcontainer should use ${localEnv:EDITOR} for editor choice."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="vi",
            global_settings=self._make_global_settings(),
        )

        result = _generate_scratch_devcontainer(ctx)
        assert "remoteEnv" in result
        assert result["remoteEnv"]["EDITOR"] == "${localEnv:EDITOR}"

    def test_editor_uses_local_env_in_extend(self, tmp_path: Path):
        """Extended devcontainer should use ${localEnv:EDITOR} for editor choice."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=[],
            editor_choice="nano",
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "remoteEnv" in result
        assert result["remoteEnv"]["EDITOR"] == "${localEnv:EDITOR}"

    def test_no_editor_remote_env_when_none(self, tmp_path: Path):
        """Scratch devcontainer should not have EDITOR in remoteEnv when choice is 'none'."""
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
        assert "EDITOR" not in result.get("remoteEnv", {})


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

    def test_env_contains_editor_when_selected(self, tmp_path: Path):
        """Generated .env should contain EDITOR when editor_choice is not 'none'."""
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

    def test_env_omits_editor_when_none(self, tmp_path: Path):
        """Generated .env should not contain EDITOR when editor_choice is 'none'."""
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

    def test_env_uses_host_auth_when_found(self, tmp_path: Path):
        """Generated .env should use host auth path when global_auth_found is True."""
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
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_GLOBAL_AUTH_PATH=/home/user/.local/share/opencode/auth.json" in env_content

    def test_env_uses_stub_auth_when_host_not_found(self, tmp_path: Path):
        """Generated .env should use stub auth path when host auth not found and framework is a valid repo."""
        framework_repo = tmp_path / "framework"
        framework_repo.mkdir()
        (framework_repo / ".git").mkdir()
        stub_dir = framework_repo / "framework-nuts-and-bolts"
        stub_dir.mkdir()
        (stub_dir / "stub-auth.json").write_text("{}")
        (framework_repo / "framework-config").mkdir()
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_auth_found=False,
                global_auth_path=None,
                framework_repo_path=str(framework_repo),
            ),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_GLOBAL_AUTH_PATH=${OCF_LOCAL_FRAMEWORK_PATH}/framework-nuts-and-bolts/stub-auth.json" in env_content

    def test_env_auth_empty_when_no_framework_path(self, tmp_path: Path):
        """Generated .env should have empty auth path when no framework path available."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_auth_found=False,
                global_auth_path=None,
                framework_repo_path=None,
            ),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_GLOBAL_AUTH_PATH=" in env_content

    def test_env_auth_empty_when_framework_not_git_repo(self, tmp_path: Path):
        """Generated .env should have empty auth path when framework is not a git repo."""
        framework_repo = tmp_path / "framework"
        framework_repo.mkdir()
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_auth_found=False,
                global_auth_path=None,
                framework_repo_path=str(framework_repo),
            ),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_GLOBAL_AUTH_PATH=" in env_content

    def test_env_auth_empty_when_stub_file_missing(self, tmp_path: Path):
        """Generated .env should have empty auth path when stub file doesn't exist in git repo."""
        framework_repo = tmp_path / "framework"
        framework_repo.mkdir()
        (framework_repo / ".git").mkdir()
        (framework_repo / "framework-nuts-and-bolts").mkdir()
        (framework_repo / "framework-config").mkdir()
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            editor_choice="none",
            global_settings=self._make_global_settings(
                global_auth_found=False,
                global_auth_path=None,
                framework_repo_path=str(framework_repo),
            ),
        )
        
        (tmp_path / ".opencode").mkdir(exist_ok=True)
        _generate_env_file(ctx)
        
        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_GLOBAL_AUTH_PATH=" in env_content


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

    def test_launch_command_is_cli(self):
        """Launch command should use ocframework CLI."""
        commands = _get_launch_commands()
        assert commands["launch"] == "ocframework launch"

    def test_debug_command_is_cli(self):
        """Debug command should use ocframework exec CLI."""
        commands = _get_launch_commands()
        assert commands["debug"] == "ocframework exec -- opencode debug config"

    def test_shell_command_is_cli(self):
        """Shell command should use ocframework exec CLI."""
        commands = _get_launch_commands()
        assert commands["shell"] == "ocframework exec -- bash"

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

    def test_readme_shows_cli_launch(self, tmp_path: Path):
        """README should show CLI launch command."""
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
        assert "ocframework launch" in readme_content

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

    def test_readme_has_teardown_section(self, tmp_path: Path):
        """README should have teardown section."""
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
        assert "## Teardown" in readme_content
        assert "docker rm -f" in readme_content
        assert '$(basename "$(pwd)")' in readme_content


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

        generate_opencode_directory(repo_root, wizard_result)

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

        generate_opencode_directory(repo_root, wizard_result)

        runtime_data = opencode_dir / "runtime_data"
        
        assert not (runtime_data / "logs").exists()
        assert not (runtime_data / "tools").exists()
        assert not (runtime_data / "temp").exists()
        assert not (runtime_data / "sessions").exists()
        assert not (runtime_data / "output").exists()
        assert not (runtime_data / "home").exists()

    def test_no_root_gitkeep(self, tmp_path: Path):
        """Should not create root-level runtime_data/.gitkeep."""
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

        runtime_data = opencode_dir / "runtime_data"
        assert not (runtime_data / ".gitkeep").exists()

    def test_no_gitkeep_in_subdirs(self, tmp_path: Path):
        """Should not create .gitkeep files in subdirectories."""
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

        runtime_data = opencode_dir / "runtime_data"
        
        assert not (runtime_data / ".cache" / ".gitkeep").exists()
        assert not (runtime_data / ".local" / "share" / ".gitkeep").exists()
        assert not (runtime_data / ".local" / "state" / ".gitkeep").exists()

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

        generate_opencode_directory(repo_root, wizard_result)

        gitignore_content = (opencode_dir / ".gitignore").read_text()
        
        assert "runtime_data/" in gitignore_content

    def test_gitignore_ignores_node_modules(self, tmp_path: Path):
        """gitignore should ignore node_modules directory."""
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

        gitignore_content = (opencode_dir / ".gitignore").read_text()
        
        assert "node_modules/" in gitignore_content

    def test_gitignore_no_gitkeep_unignore_lines(self, tmp_path: Path):
        """gitignore should not have .gitkeep unignore lines."""
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

        gitignore_content = (opencode_dir / ".gitignore").read_text()
        
        assert "!runtime_data/.cache/.gitkeep" not in gitignore_content
        assert "!runtime_data/.local/share/.gitkeep" not in gitignore_content
        assert "!runtime_data/.local/state/.gitkeep" not in gitignore_content


class TestReadmeFrameworkUrl:
    """Tests for README framework URL."""

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

    def test_readme_has_new_framework_url(self, tmp_path: Path):
        """README should have new framework docs URL."""
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
        assert "https://github.com/dzharikhin/codeagent-infra" in readme_content
        assert "https://github.com/anomalyco/opencode-framework" not in readme_content


class TestMountMerging:
    """Tests for mount merging with string and dict mounts."""

    def test_extract_target_from_dict_mount(self):
        """Should extract target from dict mount."""
        mount = {"source": "/host/path", "target": "/container/path", "type": "bind"}
        assert _extract_mount_target(mount) == "/container/path"

    def test_extract_target_from_string_mount(self):
        """Should extract target from string mount."""
        mount = "type=bind,source=/host/path,target=/container/path,readonly"
        assert _extract_mount_target(mount) == "/container/path"

    def test_extract_target_from_dict_without_target(self):
        """Should return None for dict without target."""
        mount = {"source": "/host/path", "type": "bind"}
        assert _extract_mount_target(mount) is None

    def test_merge_string_mounts(self):
        """Should merge string mounts and dedupe by target."""
        existing = ["type=bind,source=/a,target=/x"]
        additions = ["type=bind,source=/b,target=/y", "type=bind,source=/c,target=/x"]
        
        result = _merge_mounts(existing, additions)
        
        assert len(result) == 2
        assert "target=/x" in result[0]
        assert "target=/y" in result[1]

    def test_merge_dict_mounts(self):
        """Should merge dict mounts and dedupe by target."""
        existing = [{"source": "/a", "target": "/x", "type": "bind"}]
        additions = [
            {"source": "/b", "target": "/y", "type": "bind"},
            {"source": "/c", "target": "/x", "type": "bind"},
        ]
        
        result = _merge_mounts(existing, additions)
        
        assert len(result) == 2
        assert result[0]["target"] == "/x"
        assert result[1]["target"] == "/y"

    def test_merge_mixed_mounts(self):
        """Should merge mixed string and dict mounts."""
        existing = [{"source": "/a", "target": "/x", "type": "bind"}]
        additions = ["type=bind,source=/b,target=/y", "type=bind,source=/c,target=/x"]
        
        result = _merge_mounts(existing, additions)
        
        assert len(result) == 2
