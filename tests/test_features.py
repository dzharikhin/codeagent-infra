"""Tests for interactive feature management and surgical config updates."""

import json
from pathlib import Path
from typing import List

import pytest

from opencode_framework import features
from opencode_framework.generators.compose import ComposeGenerator
from opencode_framework.generators.devcontainer import DevcontainerGenerator, COMMON_UTILS_URL
from opencode_framework.generators.templates import TemplateHandler


def _dc_with_features(*features: str, editor: str = "none") -> dict:
    """Build a devcontainer dict with the given optional features."""
    dc = {"features": {}}
    DevcontainerGenerator._add_optional_features(dc["features"], list(features), editor)
    return dc


def _render_compose(repo_name: str, features: List[str]) -> str:
    return TemplateHandler.render_compose_template(repo_name, features)


class TestDetect:
    """Tests for DevcontainerGenerator.detect."""

    def test_detects_no_features(self):
        dc = _dc_with_features()
        features, editor = DevcontainerGenerator.detect(dc)
        assert features == []
        assert editor == "none"

    def test_detects_single_feature(self):
        for key in ("docker", "python", "nodejs", "java"):
            dc = _dc_with_features(key)
            detected, _ = DevcontainerGenerator.detect(dc)
            assert detected == [key]

    def test_detects_all_features(self):
        dc = _dc_with_features("docker", "python", "nodejs", "java")
        detected, _ = DevcontainerGenerator.detect(dc)
        assert detected == ["docker", "python", "nodejs", "java"]

    def test_detect_order_follows_catalog(self):
        dc = _dc_with_features("java", "python", "docker")
        detected, _ = DevcontainerGenerator.detect(dc)
        assert detected == ["docker", "python", "java"]

    def test_detect_vi_editor(self):
        dc = _dc_with_features(editor="vi")
        _, editor = DevcontainerGenerator.detect(dc)
        assert editor == "vi"

    def test_detect_nano_editor(self):
        dc = _dc_with_features(editor="nano")
        _, editor = DevcontainerGenerator.detect(dc)
        assert editor == "nano"

    def test_detect_none_editor(self):
        dc = _dc_with_features()
        _, editor = DevcontainerGenerator.detect(dc)
        assert editor == "none"

    def test_detect_preserves_unknown_features(self):
        """Detect should ignore features it doesn't manage."""
        dc = {
            "features": {
                "ghcr.io/some/other/feature:1": {"foo": "bar"},
                DevcontainerGenerator.FEATURE_URL_MAP["python"]: {},
            }
        }
        detected, editor = DevcontainerGenerator.detect(dc)
        assert detected == ["python"]
        assert editor == "none"

    def test_detect_handles_missing_features_key(self):
        detected, editor = DevcontainerGenerator.detect({})
        assert detected == []
        assert editor == "none"

    def test_detect_handles_non_dict_features(self):
        detected, editor = DevcontainerGenerator.detect({"features": "not a dict"})
        assert detected == []
        assert editor == "none"


class TestApplyDelta:
    """Tests for DevcontainerGenerator.apply_delta."""

    def test_add_feature(self):
        dc = {"features": {}}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[], editor="none")
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] in dc["features"]

    def test_remove_feature(self):
        dc = _dc_with_features("python", "docker")
        DevcontainerGenerator.apply_delta(dc, add=[], remove=["python"], editor="none")
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] not in dc["features"]
        assert DevcontainerGenerator.FEATURE_URL_MAP["docker"] in dc["features"]

    def test_preserves_unrelated_features(self):
        """Custom features and params must survive a delta."""
        custom_url = "ghcr.io/some/custom:1"
        dc = {"features": {custom_url: {"token": "secret"}}}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[], editor="none")
        assert custom_url in dc["features"]
        assert dc["features"][custom_url] == {"token": "secret"}

    def test_preserves_custom_feature_params_on_toggle(self):
        """Removing one feature must not reset another's params."""
        dc = _dc_with_features("python", "java")
        python_url = DevcontainerGenerator.FEATURE_URL_MAP["python"]
        dc["features"][python_url]["version"] = "3.11"
        DevcontainerGenerator.apply_delta(dc, add=[], remove=["java"], editor="none")
        assert dc["features"][python_url]["version"] == "3.11"

    def test_set_editor_adds_vim(self):
        dc = _dc_with_features()
        DevcontainerGenerator.apply_delta(dc, add=[], remove=[], editor="vi")
        packages = dc["features"][COMMON_UTILS_URL]["installPackages"]
        assert "vim" in packages

    def test_set_editor_toggle_removes_vim(self):
        """Toggling editor to 'none' should remove vim (unlike init guard)."""
        dc = _dc_with_features(editor="vi")
        DevcontainerGenerator.apply_delta(dc, add=[], remove=[], editor="none")
        packages = dc["features"][COMMON_UTILS_URL]["installPackages"]
        assert packages is None or "vim" not in packages

    def test_set_editor_preserves_other_packages(self):
        """Changing editor must not drop packages like ripgrep."""
        dc = {"features": {COMMON_UTILS_URL: {"installPackages": "ripgrep vim"}}}
        DevcontainerGenerator.apply_delta(dc, add=[], remove=[], editor="nano")
        packages = dc["features"][COMMON_UTILS_URL]["installPackages"]
        assert "ripgrep" in packages
        assert "nano" in packages
        assert "vim" not in packages

    def test_apply_delta_returns_same_object(self):
        """apply_delta mutates and returns the passed-in dict."""
        dc = {"features": {}}
        result = DevcontainerGenerator.apply_delta(dc, add=["docker"], remove=[], editor="none")
        assert result is dc

    def test_apply_delta_creates_features_key_if_missing(self):
        dc = {}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[], editor="none")
        assert "features" in dc
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] in dc["features"]


class TestRebuildFeatures:
    """Tests for ComposeGenerator.rebuild_features."""

    REPO = "myrepo"

    def _rebuild(self, text: str, features: List[str]) -> str:
        return ComposeGenerator.rebuild_features(text, self.REPO, features)

    def assert_managed(self, text: str, features: List[str]) -> None:
        has_docker = "docker" in features
        assert ("    privileged: true" in text.split("\n")) is has_docker
        assert ('docker-init.sh' in text) is has_docker
        assert (f"venv-{self.REPO}:/{self.REPO}/.venv" in text) is ("python" in features)
        assert (f"m2-{self.REPO}:/home" in text) is ("java" in features)
        if "python" in features or "java" in features:
            assert "\nvolumes:" in text
        else:
            assert "\nvolumes:" not in text

    def test_no_change_roundtrip(self):
        for feats in ([], ["python"], ["java"], ["docker"],
                      ["python", "java"], ["python", "java", "docker"], ["nodejs"]):
            text = _render_compose(self.REPO, feats)
            rebuilt = self._rebuild(text, feats)
            self.assert_managed(rebuilt, feats)

    def test_idempotent(self):
        """Applying the same feature set twice yields identical output."""
        for feats in ([], ["python"], ["java", "docker"], ["python", "java", "docker"]):
            text = _render_compose(self.REPO, feats)
            once = self._rebuild(text, feats)
            twice = self._rebuild(once, feats)
            assert once == twice, f"Not idempotent for {feats}"

    def test_add_python_to_empty(self):
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["python"])
        self.assert_managed(rebuilt, ["python"])
        assert f"  venv-{self.REPO}:" in rebuilt.split("\n")

    def test_remove_python(self):
        text = _render_compose(self.REPO, ["python"])
        rebuilt = self._rebuild(text, [])
        self.assert_managed(rebuilt, [])
        assert f"venv-{self.REPO}:" not in rebuilt
        assert "\nvolumes:" not in rebuilt

    def test_toggle_docker_on(self):
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["docker"])
        assert '["/usr/local/share/docker-init.sh", "opencode"]' in rebuilt
        assert "    privileged: true" in rebuilt.split("\n")

    def test_toggle_docker_off(self):
        text = _render_compose(self.REPO, ["docker"])
        rebuilt = self._rebuild(text, [])
        assert '["opencode"]' in rebuilt
        assert "    privileged: true" not in rebuilt.split("\n")

    def test_all_transitions_consistent(self):
        """Every add/remove transition must match the rendered target."""
        sets = [[], ["python"], ["java"], ["docker"],
                ["python", "java"], ["python", "java", "docker"]]
        for src in sets:
            for dst in sets:
                rebuilt = self._rebuild(_render_compose(self.REPO, src), dst)
                self.assert_managed(rebuilt, dst)

    def test_preserves_manual_env_var(self):
        """User-added environment lines must survive rebuild."""
        text = _render_compose(self.REPO, [])
        text = text.replace(
            "      - OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT=true",
            "      - OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT=true\n      - MY_CUSTOM=keepme",
            1,
        )
        rebuilt = self._rebuild(text, ["python", "docker"])
        assert "MY_CUSTOM=keepme" in rebuilt

    def test_preserves_user_top_level_volume(self):
        """A user-defined top-level volume must survive alongside managed ones."""
        text = _render_compose(self.REPO, ["python"])
        text = text.replace(
            "volumes:\n  venv-myrepo:",
            "volumes:\n  user-keepvol:\n  venv-myrepo:",
        )
        rebuilt = self._rebuild(text, ["python", "java", "docker"])
        assert "  user-keepvol:" in rebuilt.split("\n")
        assert "  venv-myrepo:" in rebuilt.split("\n")
        assert "  m2-myrepo:" in rebuilt.split("\n")

    def test_volumes_header_not_duplicated(self):
        """Rebuilding must not create two top-level volumes: keys."""
        text = _render_compose(self.REPO, ["python"])
        rebuilt = self._rebuild(text, ["python", "java"])
        assert rebuilt.count("\nvolumes:") == 1

    def test_service_volumes_key_not_confused(self):
        """The indented service-level 'volumes:' key must not receive top-level keys."""
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["python"])
        lines = rebuilt.split("\n")
        svc_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "volumes:" and ln.startswith(" "))
        # the line right after the service-level volumes: key must be a mount, not a top-level key
        assert lines[svc_idx + 1].startswith("      - ")


class TestRenderComposeTemplateVolumeFix:
    """Regression tests for the java-without-python volumes: header bug."""

    def test_java_only_has_volumes_header(self):
        text = _render_compose("repo", ["java"])
        assert "\nvolumes:" in text
        assert "  m2-repo:" in text.split("\n")

    def test_java_only_not_orphaned_under_services(self):
        """The m2 volume key must live under top-level volumes:, not services."""
        text = _render_compose("repo", ["java"])
        lines = text.split("\n")
        vol_idx = next(i for i, ln in enumerate(lines) if ln == "volumes:")
        assert lines[vol_idx + 1] == "  m2-repo:"

    def test_python_and_java_both_volumes(self):
        text = _render_compose("repo", ["python", "java"])
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo:" in text.split("\n")
        assert "  m2-repo:" in text.split("\n")

    def test_no_features_no_volumes(self):
        text = _render_compose("repo", [])
        assert "\nvolumes:" not in text


class TestUpdateFeatures:
    """Tests for the high-level features.update_features orchestrator."""

    def _seed_opencode(self, tmp_path: Path, features_list: List[str]) -> Path:
        """Create a minimal .opencode dir with devcontainer.json + compose."""
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        dc = {"features": {}}
        DevcontainerGenerator._add_optional_features(dc["features"], features_list, "none")
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc))
        (opencode_dir / "docker-compose.yaml").write_text(
            TemplateHandler.render_compose_template(tmp_path.name, features_list)
        )
        return opencode_dir

    def test_non_interactive_returns_false_and_is_noop(self, tmp_path: Path, monkeypatch):
        """Without a TTY, update_features must not prompt or write."""
        monkeypatch.setattr(features, "is_interactive", lambda: False)
        opencode_dir = self._seed_opencode(tmp_path, ["python"])

        dc_before = (opencode_dir / "devcontainer.json").read_text()
        compose_before = (opencode_dir / "docker-compose.yaml").read_text()

        result = features.update_features(opencode_dir, tmp_path.name)

        assert result is False
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before
        assert (opencode_dir / "docker-compose.yaml").read_text() == compose_before

    def test_unreadable_devcontainer_returns_false(self, tmp_path: Path, monkeypatch):
        """A broken devcontainer.json should not crash, just skip."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{ not valid json")

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is False

    def test_no_change_returns_false(self, tmp_path: Path, monkeypatch):
        """When the user keeps the same selection, files are untouched."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed: (list(cur), ed),
        )
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is False
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before

    def test_change_writes_both_files(self, tmp_path: Path, monkeypatch):
        """A feature change must update devcontainer.json and compose."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        # Simulate the user adding docker + java to an existing python setup.
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed: (["python", "docker", "java"], ed),
        )
        opencode_dir = self._seed_opencode(tmp_path, ["python"])

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True

        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected, _ = DevcontainerGenerator.detect(dc)
        assert set(detected) == {"python", "docker", "java"}

        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "docker-init.sh" in compose
        assert f"m2-{tmp_path.name}:/home" in compose

    def test_change_without_compose_only_updates_devcontainer(self, tmp_path: Path, monkeypatch):
        """If docker-compose.yaml is absent, only devcontainer.json is updated."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed: (["python"], ed),
        )
        opencode_dir = self._seed_opencode(tmp_path, [])
        (opencode_dir / "docker-compose.yaml").unlink()

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected, _ = DevcontainerGenerator.detect(dc)
        assert detected == ["python"]


class TestInteractiveDetection:
    """Tests for features.is_interactive."""

    def test_non_tty_returns_false(self, monkeypatch):
        class _FakeStdin:
            def isatty(self):
                return False

        monkeypatch.setattr(features.sys, "stdin", _FakeStdin())
        assert features.is_interactive() is False

    def test_tty_returns_true(self, monkeypatch):
        class _FakeStdin:
            def isatty(self):
                return True

        monkeypatch.setattr(features.sys, "stdin", _FakeStdin())
        assert features.is_interactive() is True

    def test_missing_isatty_returns_false(self, monkeypatch):
        class _FakeStdin:
            pass  # no isatty method

        monkeypatch.setattr(features.sys, "stdin", _FakeStdin())
        assert features.is_interactive() is False

