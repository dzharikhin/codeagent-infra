"""Tests for devcontainer detection and compatibility."""

import json
from pathlib import Path


from opencode_framework.devcontainer import (
    detect_devcontainer,
    evaluate_compatibility,
)


class TestDetectDevcontainer:
    """Tests for devcontainer detection."""

    def test_no_devcontainer(self, tmp_path: Path):
        """Should return None when no devcontainer exists."""
        result = detect_devcontainer(tmp_path)
        assert result is None

    def test_detect_devcontainer_json(self, tmp_path: Path):
        """Should detect .devcontainer/devcontainer.json."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir()
        dc_file = dc_dir / "devcontainer.json"
        dc_file.write_text(json.dumps({"image": "ubuntu:22.04"}))

        result = detect_devcontainer(tmp_path)
        assert result is not None
        assert result.format == "json"
        assert result.compatible is True

    def test_detect_root_devcontainer_json(self, tmp_path: Path):
        """Should detect .devcontainer.json at root."""
        dc_file = tmp_path / ".devcontainer.json"
        dc_file.write_text(json.dumps({"image": "ubuntu:22.04"}))

        result = detect_devcontainer(tmp_path)
        assert result is not None
        assert result.format == "json"
        assert ".devcontainer.json" in result.path

    def test_detect_yaml_format(self, tmp_path: Path):
        """Should detect YAML devcontainer files."""
        dc_dir = tmp_path / ".devcontainer"
        dc_dir.mkdir()
        dc_file = dc_dir / "devcontainer.yaml"
        dc_file.write_text("image: ubuntu:22.04\n")

        result = detect_devcontainer(tmp_path)
        assert result is not None
        assert result.format == "yaml"

    def test_invalid_json(self, tmp_path: Path):
        """Should mark invalid JSON as incompatible."""
        dc_file = tmp_path / ".devcontainer.json"
        dc_file.write_text("{ not valid json }")

        result = detect_devcontainer(tmp_path)
        assert result is not None
        assert result.compatible is False
        assert "Invalid JSON" in result.incompatibility_reason


class TestEvaluateCompatibility:
    """Tests for devcontainer compatibility evaluation."""

    def test_compatible_with_image(self):
        """Devcontainer with image should be compatible."""
        content = {"image": "mcr.microsoft.com/devcontainers/base:ubuntu-22.04"}
        compatible, reason = evaluate_compatibility(content)
        assert compatible is True
        assert reason is None

    def test_compatible_with_build(self):
        """Devcontainer with build should be compatible."""
        content = {"build": {"dockerfile": "Dockerfile"}}
        compatible, reason = evaluate_compatibility(content)
        assert compatible is True
        assert reason is None

    def test_incompatible_no_image_or_build(self):
        """Devcontainer without image or build should be incompatible."""
        content = {"name": "test"}
        compatible, reason = evaluate_compatibility(content)
        assert compatible is False
        assert "No 'image' or 'build'" in reason
