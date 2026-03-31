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
            existing_devcontainer=None,
            should_add_to_gitignore=True,
        )

        generate_opencode_directory(repo_root, wizard_result)

        assert (opencode_dir / "devcontainer.json").exists()
        assert (opencode_dir / ".env").exists()
        assert (opencode_dir / "README.md").exists()
        assert (opencode_dir / ".gitignore").exists()
        assert (opencode_dir / "opencode.json").exists()
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
        _add_optional_features(features, ["docker"])
        assert "ghcr.io/devcontainers/features/docker-in-docker:2" in features

    def test_python_feature(self):
        """Python feature should add Python feature."""
        features = {}
        _add_optional_features(features, ["python"])
        assert "ghcr.io/devcontainers/features/python:1" in features

    def test_nodejs_feature(self):
        """Node.js feature should add Node feature."""
        features = {}
        _add_optional_features(features, ["nodejs"])
        assert "ghcr.io/devcontainers/features/node:1" in features

    def test_java_feature(self):
        """Java feature should add Java feature."""
        features = {}
        _add_optional_features(features, ["java"])
        assert "ghcr.io/devcontainers/features/java:1" in features

    def test_vi_feature(self):
        """vi feature should add vim to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        _add_optional_features(features, ["vi"])
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "vim" in common_utils["installPackages"]

    def test_nano_feature(self):
        """nano feature should add nano to common-utils packages."""
        features = {"ghcr.io/devcontainers/features/common-utils:2": {}}
        _add_optional_features(features, ["nano"])
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" in common_utils
        assert "nano" in common_utils["installPackages"]


class TestExtendedDevcontainer:
    """Tests for extended devcontainer generation."""

    def _make_global_settings(self, **kwargs):
        """Create GlobalSettings with defaults."""
        defaults = {
            "framework_repo_path": None,
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
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert "ghcr.io/devcontainers/features/python:1" in result["features"]
        assert "ghcr.io/devcontainers/features/node:1" in result["features"]

    def test_docker_env_set(self, tmp_path: Path):
        """Extended devcontainer with Docker should set rootless env."""
        existing = {"image": "ubuntu:22.04"}
        
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="extend",
            optional_features=["docker"],
            global_settings=self._make_global_settings(),
            existing_devcontainer=existing,
        )

        result = _generate_extended_devcontainer(ctx)
        assert result["remoteEnv"]["DOCKER_CONTEXT"] == "rootless"


class TestBuildMounts:
    """Tests for mount building."""

    def _make_global_settings(self, **kwargs):
        """Create GlobalSettings with defaults."""
        defaults = {
            "framework_repo_path": None,
            "global_config_found": False,
            "global_config_path": None,
            "global_auth_found": False,
            "global_auth_path": None,
        }
        defaults.update(kwargs)
        return GlobalSettings(**defaults)

    def test_no_global_settings(self, tmp_path: Path):
        """Should return empty mounts when no global settings."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
            global_settings=self._make_global_settings(),
        )

        mounts = _build_mounts(ctx)
        assert mounts == []

    def test_global_config_mount(self, tmp_path: Path):
        """Should mount global config read-only."""
        ctx = GenerationContext(
            repo_root=tmp_path,
            opencode_dir=tmp_path / ".opencode",
            branch_name="codeagent-test",
            devcontainer_strategy="from_scratch",
            optional_features=[],
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
            global_settings=self._make_global_settings(
                global_auth_found=True,
                global_auth_path="/home/user/.local/share/opencode/auth.json",
            ),
        )

        mounts = _build_mounts(ctx)
        auth_mounts = [m for m in mounts if "auth.json" in m["target"]]
        assert len(auth_mounts) == 1
        assert auth_mounts[0]["readOnly"] is True
