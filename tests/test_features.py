"""Tests for interactive feature management and surgical config updates."""

import json
from pathlib import Path
from typing import List

import pytest

from opencode_framework.generators.templates import (
    GITCONFIG_MOUNT_LINE,
    GRADLE_ENV_COMMENT,
    GRADLE_OPTS_LINE,
    M2_SETTINGS_MOUNT_LINE,
    NPMRC_MOUNT_LINE,
    SSH_MOUNT_LINE,
    TemplateHandler,
)
from opencode_framework.sandbox import features
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.devcontainer import DevcontainerGenerator


def _dc_with_features(*features: str) -> dict:
    """Build a devcontainer dict with the given optional features."""
    dc = {"features": {}}
    DevcontainerGenerator._add_optional_features(dc["features"], list(features))
    return dc


def _render_compose(
    repo_name: str,
    features: List[str],
    ports: List[str] = None,
    java_build_tools: List[str] = None,
) -> str:
    return TemplateHandler.render_compose_template(
        repo_name, features, ports, java_build_tools
    )


def _render_compose_caps(
    repo_name: str,
    features: List[str],
    ports: List[str] = None,
    java_build_tools: List[str] = None,
) -> str:
    return TemplateHandler.render_compose_template(
        repo_name, features, ports, java_build_tools, podman_caps=True
    )


class TestDetect:
    """Tests for DevcontainerGenerator.detect."""

    def test_detects_no_features(self):
        dc = _dc_with_features()
        detected = DevcontainerGenerator.detect(dc)
        assert detected == []

    def test_detects_single_feature(self):
        for key in ("python", "nodejs", "java"):
            dc = _dc_with_features(key)
            detected = DevcontainerGenerator.detect(dc)
            assert detected == [key]

    def test_detects_docker_feature(self):
        dc = _dc_with_features("docker")
        detected = DevcontainerGenerator.detect(dc)
        assert "docker" in detected

    def test_detects_ssh_feature(self):
        """The ssh footprint (openssh-client apt package) is detected."""
        dc = _dc_with_features("ssh")
        detected = DevcontainerGenerator.detect(dc)
        assert "ssh" in detected

    def test_ssh_not_detected_without_package(self):
        dc = _dc_with_features("python")
        detected = DevcontainerGenerator.detect(dc)
        assert "ssh" not in detected

    def test_detects_all_features(self):
        dc = _dc_with_features("docker", "python", "nodejs", "java")
        detected = DevcontainerGenerator.detect(dc)
        assert set(detected) == {"docker", "python", "nodejs", "java"}

    def test_detect_legacy_dind_as_docker(self):
        """Legacy docker-in-docker:2 URL should be reported as docker feature."""
        dc = {
            "features": {
                DevcontainerGenerator.LEGACY_DIND_FEATURE_URL: {"version": "latest"},
                DevcontainerGenerator.FEATURE_URL_MAP["python"]: {},
            }
        }
        detected = DevcontainerGenerator.detect(dc)
        assert "docker" in detected
        assert "python" in detected

    def test_detect_order_follows_catalog(self):
        dc = _dc_with_features("java", "python", "docker")
        detected = DevcontainerGenerator.detect(dc)
        assert "python" in detected
        assert "java" in detected
        assert "docker" in detected

    def test_detect_preserves_unknown_features(self):
        """Detect should ignore features it doesn't manage."""
        dc = {
            "features": {
                "ghcr.io/some/other/feature:1": {"foo": "bar"},
                DevcontainerGenerator.FEATURE_URL_MAP["python"]: {},
            }
        }
        detected = DevcontainerGenerator.detect(dc)
        assert detected == ["python"]

    def test_detect_handles_missing_features_key(self):
        detected = DevcontainerGenerator.detect({})
        assert detected == []

    def test_detect_handles_non_dict_features(self):
        detected = DevcontainerGenerator.detect({"features": "not a dict"})
        assert detected == []

    def test_detect_build_tools_maven_only(self):
        dc = _dc_with_features("java")
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installMaven"
        ] = True
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installGradle"
        ] = False
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == ["maven"]

    def test_detect_build_tools_gradle_only(self):
        dc = _dc_with_features("java")
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installMaven"
        ] = False
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installGradle"
        ] = True
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == ["gradle"]

    def test_detect_build_tools_both(self):
        dc = _dc_with_features("java")
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installMaven"
        ] = True
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installGradle"
        ] = True
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == ["maven", "gradle"]

    def test_detect_build_tools_none_explicit(self):
        dc = _dc_with_features("java")
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installMaven"
        ] = False
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installGradle"
        ] = False
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == []

    def test_detect_build_tools_no_flags_returns_empty(self):
        """Java present but no build flags → no tools (no compat default)."""
        dc = _dc_with_features("java")
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == []

    def test_detect_build_tools_no_java(self):
        dc = _dc_with_features("python")
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == []

    def test_detect_build_tools_mixed_features(self):
        dc = _dc_with_features("python", "java", "nodejs")
        dc["features"][DevcontainerGenerator.FEATURE_URL_MAP["java"]][
            "installGradle"
        ] = True
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == ["gradle"]


class TestReconcile:
    """Tests for DevcontainerGenerator._reconcile_java_build_tools."""

    def test_reconcile_maven_only(self):
        dc = _dc_with_features("java")
        DevcontainerGenerator._reconcile_java_build_tools(dc["features"], ["maven"])
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert dc["features"][java_url]["installMaven"] is True
        assert dc["features"][java_url]["installGradle"] is False

    def test_reconcile_gradle_only(self):
        dc = _dc_with_features("java")
        DevcontainerGenerator._reconcile_java_build_tools(dc["features"], ["gradle"])
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert dc["features"][java_url]["installMaven"] is False
        assert dc["features"][java_url]["installGradle"] is True

    def test_reconcile_both(self):
        dc = _dc_with_features("java")
        DevcontainerGenerator._reconcile_java_build_tools(
            dc["features"], ["maven", "gradle"]
        )
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert dc["features"][java_url]["installMaven"] is True
        assert dc["features"][java_url]["installGradle"] is True

    def test_reconcile_none(self):
        dc = _dc_with_features("java")
        DevcontainerGenerator._reconcile_java_build_tools(dc["features"], [])
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert dc["features"][java_url]["installMaven"] is False
        assert dc["features"][java_url]["installGradle"] is False

    def test_reconcile_preserves_existing_params(self):
        dc = _dc_with_features("java")
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        dc["features"][java_url]["version"] = "21"
        dc["features"][java_url]["custom"] = "keep"
        DevcontainerGenerator._reconcile_java_build_tools(dc["features"], ["gradle"])
        assert dc["features"][java_url]["version"] == "21"
        assert dc["features"][java_url]["custom"] == "keep"
        assert dc["features"][java_url]["installMaven"] is False
        assert dc["features"][java_url]["installGradle"] is True

    def test_reconcile_none_java_not_in_features(self):
        """No change when Java feature not present."""
        dc = {"features": {}}
        DevcontainerGenerator._reconcile_java_build_tools(dc["features"], ["maven"])
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert java_url not in dc["features"]


class TestApplyDelta:
    """Tests for DevcontainerGenerator.apply_delta."""

    def test_add_feature(self):
        dc = {"features": {}}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[])
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] in dc["features"]

    def test_remove_feature(self):
        dc = _dc_with_features("python")
        DevcontainerGenerator.apply_delta(dc, add=[], remove=["python"])
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] not in dc["features"]

    def test_preserves_unrelated_features(self):
        """Custom features and params must survive a delta."""
        custom_url = "ghcr.io/some/custom:1"
        dc = {"features": {custom_url: {"token": "secret"}}}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[])
        assert custom_url in dc["features"]
        assert dc["features"][custom_url] == {"token": "secret"}

    def test_preserves_custom_feature_params_on_toggle(self):
        """Removing one feature must not reset another's params."""
        dc = _dc_with_features("python", "java")
        python_url = DevcontainerGenerator.FEATURE_URL_MAP["python"]
        dc["features"][python_url]["version"] = "3.11"
        DevcontainerGenerator.apply_delta(dc, add=[], remove=["java"])
        assert dc["features"][python_url]["version"] == "3.11"

    def test_apply_delta_returns_same_object(self):
        """apply_delta mutates and returns the passed-in dict."""
        dc = {"features": {}}
        result = DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[])
        assert result is dc

    def test_apply_delta_creates_features_key_if_missing(self):
        dc = {}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[])
        assert "features" in dc
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] in dc["features"]

    def test_add_ssh_merges_apt_package(self):
        """ssh merges openssh-client into apt-packages, keeping docker's."""
        dc = _dc_with_features("docker")
        DevcontainerGenerator.apply_delta(dc, add=["ssh"], remove=[])
        entry = dc["features"][DevcontainerGenerator.APT_PACKAGES_FEATURE_URL]
        packages = entry["packages"].split(",")
        assert "openssh-client" in packages
        assert "podman" in packages

    def test_remove_ssh_filters_apt_package(self):
        """Removing ssh drops only openssh-client, keeping docker's."""
        dc = _dc_with_features("docker", "ssh")
        DevcontainerGenerator.apply_delta(dc, add=[], remove=["ssh"])
        entry = dc["features"][DevcontainerGenerator.APT_PACKAGES_FEATURE_URL]
        packages = entry["packages"].split(",")
        assert "openssh-client" not in packages
        assert "podman" in packages


class TestRebuildFeatures:
    """Tests for ComposeGenerator.rebuild_features."""

    REPO = "myrepo"

    @pytest.fixture(autouse=True)
    def _deterministic_ssh_probe(self, monkeypatch):
        """Pin the host ~/.ssh probe for both render and reconcile paths."""
        probe = lambda enabled: "/home/alice/.ssh" if enabled else ""  # noqa: E731
        monkeypatch.setattr(
            "opencode_framework.generators.templates.host_ssh_dir_path", probe
        )
        monkeypatch.setattr(
            "opencode_framework.sandbox.compose.host_ssh_dir_path", probe
        )

    def _rebuild(
        self, text: str, features: List[str], java_build_tools: List[str] = None
    ) -> str:
        return ComposeGenerator.rebuild_features(
            text, self.REPO, features, java_build_tools=java_build_tools
        )

    def assert_managed(
        self, text: str, features: List[str], java_build_tools: List[str] = None
    ) -> None:
        has_docker = "docker" in features
        assert ("    privileged: true" in text.split("\n")) is False
        assert ("    init: true" in text.split("\n")) is True
        assert "docker-init.sh" not in text
        assert ("seccomp=unconfined" in text) is has_docker
        assert ("/dev/fuse" in text) is has_docker
        # Podman graph-root volume is pinned at /home/vscode/.local/share/containers
        assert (
            f"docker-{self.REPO}-opencode:/home/vscode/.local/share/containers" in text
        ) is has_docker
        # Python venv volume is mounted at ${OCF_LOCAL_REPO_ROOT:-${PWD}}/.venv
        assert (
            f"venv-{self.REPO}-opencode:${{OCF_LOCAL_REPO_ROOT:-${{PWD}}}}/.venv"
            in text
        ) is ("python" in features)
        # Maven m2 volume is mounted at /home/${REMOTE_USER}/.m2
        assert (f"m2-{self.REPO}-opencode:/home/${{REMOTE_USER}}/.m2" in text) is (
            "java" in features and ("maven" in (java_build_tools or []))
        )
        # Gradle home volume is mounted at /home/${REMOTE_USER}/.gradle
        assert (
            f"gradle-{self.REPO}-opencode:/home/${{REMOTE_USER}}/.gradle" in text
        ) is ("java" in features and ("gradle" in (java_build_tools or [])))
        # Host ~/.npmrc mirror mount is tool-agnostic and always present
        assert NPMRC_MOUNT_LINE in text
        # Host ~/.gitconfig mirror mount is tool-agnostic and always present
        assert GITCONFIG_MOUNT_LINE in text
        # Host ~/.ssh mirror mount accompanies the ssh feature
        assert (SSH_MOUNT_LINE in text) is ("ssh" in features)
        # Host ~/.m2/settings.xml mirror mount accompanies the Maven feature
        assert (M2_SETTINGS_MOUNT_LINE in text) is (
            "java" in features and ("maven" in (java_build_tools or []))
        )
        if (
            "python" in features
            or (
                "java" in features
                and (
                    "maven" in (java_build_tools or [])
                    or "gradle" in (java_build_tools or [])
                )
            )
            or has_docker
        ):
            assert "\nvolumes:" in text
        else:
            assert "\nvolumes:" not in text

    def test_no_change_roundtrip(self):
        for feats in (
            [],
            ["python"],
            ["java"],
            ["docker"],
            ["python", "java"],
            ["python", "java", "docker"],
            ["nodejs"],
            ["ssh"],
            ["python", "ssh"],
        ):
            text = _render_compose(self.REPO, feats)
            rebuilt = self._rebuild(text, feats)
            self.assert_managed(rebuilt, feats)

    def test_idempotent(self):
        """Applying the same feature set twice yields identical output."""
        for feats in (
            [],
            ["python"],
            ["java"],
            ["java", "docker"],
            ["python", "java", "docker"],
        ):
            text = _render_compose(self.REPO, feats)
            once = self._rebuild(text, feats)
            twice = self._rebuild(once, feats)
            assert once == twice, f"Not idempotent for {feats}"

    def test_add_python_to_empty(self):
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["python"])
        self.assert_managed(rebuilt, ["python"])
        assert f"  venv-{self.REPO}-opencode:" in rebuilt.split("\n")

    def test_remove_python(self):
        text = _render_compose(self.REPO, ["python"])
        rebuilt = self._rebuild(text, [])
        self.assert_managed(rebuilt, [])
        assert f"venv-{self.REPO}-opencode:" not in rebuilt
        assert "\nvolumes:" not in rebuilt

    def test_toggle_docker_on(self):
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["docker"])
        assert '["opencode"]' in rebuilt
        assert "seccomp=unconfined" in rebuilt
        assert (
            f"docker-{self.REPO}-opencode:/home/vscode/.local/share/containers"
            in rebuilt
        )

    def test_toggle_docker_off(self):
        text = _render_compose(self.REPO, ["docker"])
        rebuilt = self._rebuild(text, [])
        assert '["opencode"]' in rebuilt
        assert "seccomp=unconfined" not in rebuilt
        assert f"docker-{self.REPO}-opencode" not in rebuilt

    def test_toggle_ssh_on(self):
        text = _render_compose(self.REPO, [])
        rebuilt = self._rebuild(text, ["ssh"])
        assert SSH_MOUNT_LINE in rebuilt
        assert GITCONFIG_MOUNT_LINE in rebuilt

    def test_toggle_ssh_off(self):
        text = _render_compose(self.REPO, ["ssh"])
        rebuilt = self._rebuild(text, [])
        assert SSH_MOUNT_LINE not in rebuilt

    def test_ssh_mount_omitted_when_host_dir_missing(self, monkeypatch):
        """No /dev/null fallback: the line is dropped when ~/.ssh is absent."""
        monkeypatch.setattr(
            "opencode_framework.generators.templates.host_ssh_dir_path",
            lambda enabled: "",
        )
        monkeypatch.setattr(
            "opencode_framework.sandbox.compose.host_ssh_dir_path", lambda enabled: ""
        )
        text = _render_compose(self.REPO, ["ssh"])
        assert SSH_MOUNT_LINE not in text
        rebuilt = self._rebuild(text, ["ssh"])
        assert SSH_MOUNT_LINE not in rebuilt

    def test_legacy_harness_gains_gitconfig_mount(self):
        """A pre-gitconfig compose gains the mirror line on any rebuild."""
        text = _render_compose(self.REPO, ["python"]).replace(
            GITCONFIG_MOUNT_LINE + "\n", ""
        )
        assert GITCONFIG_MOUNT_LINE not in text
        rebuilt = self._rebuild(text, ["python"])
        assert GITCONFIG_MOUNT_LINE in rebuilt

    def test_legacy_dind_stripped_on_rebuild(self):
        """Legacy DinD footprint (privileged + docker-init entrypoint) is stripped."""
        # Simulate old compose with DinD footprint
        text = _render_compose(self.REPO, [])
        legacy_ep = '["/usr/local/share/docker-init.sh", "opencode"]'
        text = text.replace(
            '    entrypoint: ["opencode"]',
            f"    privileged: true\n    entrypoint: {legacy_ep}",
        )
        text = text.replace(
            "    entrypoint:",
            f"      - docker-{self.REPO}-opencode:/var/lib/docker\n    entrypoint:",
        )
        rebuilt = self._rebuild(text, [])
        assert "privileged" not in rebuilt
        assert "docker-init.sh" not in rebuilt
        assert f"docker-{self.REPO}-opencode:/var/lib/docker" not in rebuilt
        assert '["opencode"]' in rebuilt

    def test_legacy_remote_user_graph_root_migrated(self):
        """Pre-wrapper graph-root mount (REMOTE_USER-relative home) is
        rewritten to the pinned /home/vscode target."""
        text = _render_compose(self.REPO, ["docker"]).replace(
            "/home/vscode/.local/share/containers",
            "/home/${REMOTE_USER}/.local/share/containers",
        )
        rebuilt = self._rebuild(text, ["docker"])
        assert "/home/${REMOTE_USER}/.local/share/containers" not in rebuilt
        assert f"docker-{self.REPO}-opencode:/home/vscode/.local/share/containers" in (
            rebuilt
        )

    def test_all_transitions_consistent(self):
        """Every add/remove transition must match the rendered target."""
        sets = [
            [],
            ["python"],
            ["java"],
            ["docker"],
            ["python", "java"],
            ["python", "java", "docker"],
        ]
        for src in sets:
            for dst in sets:
                rebuilt = self._rebuild(_render_compose(self.REPO, src), dst)
                self.assert_managed(rebuilt, dst)

    def test_preserves_manual_env_var(self):
        """User-added environment lines must survive rebuild."""
        text = _render_compose(self.REPO, [])
        text = text.replace(
            "      - XDG_CACHE_HOME=${XDG_CACHE_HOME:-/${REMOTE_USER}/.cache}",
            "      - XDG_CACHE_HOME=${XDG_CACHE_HOME:-/${REMOTE_USER}/.cache}"
            "\n      - MY_CUSTOM=keepme",
            1,
        )
        rebuilt = self._rebuild(text, ["python", "docker"])
        assert "MY_CUSTOM=keepme" in rebuilt

    def test_preserves_user_top_level_volume(self):
        """A user-defined top-level volume must survive alongside managed ones."""
        text = _render_compose(self.REPO, ["python"])
        text = text.replace(
            "volumes:\n  venv-myrepo-opencode:",
            "volumes:\n  user-keepvol:\n  venv-myrepo-opencode:",
        )
        rebuilt = self._rebuild(
            text, ["python", "java", "docker"], java_build_tools=["maven"]
        )
        assert "  user-keepvol:" in rebuilt.split("\n")
        assert "  venv-myrepo-opencode:" in rebuilt.split("\n")
        assert "  m2-myrepo-opencode:" in rebuilt.split("\n")

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
        svc_idx = next(
            i
            for i, ln in enumerate(lines)
            if ln.strip() == "volumes:" and ln.startswith(" ")
        )
        # the line after a service-level volumes: key must be a mount,
        # not a top-level key
        assert lines[svc_idx + 1].startswith("      - ")

    def test_gradle_mount_adds_gradle_volume_to_managed_lines(self):
        """Gradle mount is added to managed_lines and thus stripped/re-added."""
        # Render with gradle, then rebuild with maven only
        text = _render_compose(self.REPO, ["java"], java_build_tools=["gradle"])
        rebuilt = self._rebuild(text, ["java"], java_build_tools=["maven"])
        # gradle mount should be removed (no longer in maven set)
        assert "gradle-" not in rebuilt

    def test_gradle_rebuild_from_maven_to_gradle(self):
        """Transition from maven to gradle replaces m2 with gradle mount."""
        text = _render_compose(self.REPO, ["java"], java_build_tools=["maven"])
        rebuilt = self._rebuild(text, ["java"], java_build_tools=["gradle"])
        assert "m2-" not in rebuilt
        assert "gradle-" in rebuilt

    def test_gradle_rebuild_from_gradle_to_maven(self):
        """Transition from gradle to maven replaces gradle with m2 mount."""
        text = _render_compose(self.REPO, ["java"], java_build_tools=["gradle"])
        rebuilt = self._rebuild(text, ["java"], java_build_tools=["maven"])
        assert "gradle-" not in rebuilt
        assert "m2-" in rebuilt

    def test_gradle_rebuild_from_maven_to_both(self):
        """Adding gradle to maven keeps both mounts."""
        text = _render_compose(self.REPO, ["java"], java_build_tools=["maven"])
        rebuilt = self._rebuild(text, ["java"], java_build_tools=["maven", "gradle"])
        assert "m2-" in rebuilt
        assert "gradle-" in rebuilt

    def test_gradle_rebuild_from_gradle_to_both(self):
        """Adding maven to gradle keeps both mounts."""
        text = _render_compose(self.REPO, ["java"], java_build_tools=["gradle"])
        rebuilt = self._rebuild(text, ["java"], java_build_tools=["maven", "gradle"])
        assert "m2-" in rebuilt
        assert "gradle-" in rebuilt

    def test_java_rebuild_to_empty_tools_removes_mounts(self):
        """Rebuilding java with empty build tools strips existing tool mounts."""
        text = _render_compose(
            self.REPO, ["java"], java_build_tools=["maven", "gradle"]
        )
        rebuilt = self._rebuild(text, ["java"], java_build_tools=[])
        self.assert_managed(rebuilt, ["java"], [])
        assert f"m2-{self.REPO}-opencode:/home" not in rebuilt
        assert f"gradle-{self.REPO}-opencode:/home" not in rebuilt

    def test_rebuild_features_accepts_java_build_tools_kwarg(self):
        """rebuild_features must accept java_build_tools as a keyword argument."""
        text = _render_compose(self.REPO, ["java"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["java"], java_build_tools=["gradle"]
        )
        assert "gradle-" in rebuilt

    def test_legacy_repo_relative_venv_mount_migrated(self):
        """Pre-OCF_LOCAL_REPO_ROOT files: legacy venv line stripped and re-added."""
        text = _render_compose(self.REPO, ["python"])
        legacy = text.replace(
            f"venv-{self.REPO}-opencode:${{OCF_LOCAL_REPO_ROOT:-${{PWD}}}}/.venv",
            f"venv-{self.REPO}-opencode:/{self.REPO}/.venv",
        )
        rebuilt = ComposeGenerator.rebuild_features(legacy, self.REPO, ["python"])
        assert f"venv-{self.REPO}-opencode:/{self.REPO}/.venv" not in rebuilt
        assert (
            f"venv-{self.REPO}-opencode:${{OCF_LOCAL_REPO_ROOT:-${{PWD}}}}/.venv"
            in rebuilt
        )

    def test_rebuild_upgrades_legacy_without_npmrc_mount(self):
        """Harnesses generated before the npmrc mount get it on rebuild."""
        text = _render_compose(self.REPO, ["python"])
        legacy = "\n".join(
            line for line in text.split("\n") if line != NPMRC_MOUNT_LINE
        )
        assert NPMRC_MOUNT_LINE not in legacy

        rebuilt = self._rebuild(legacy, ["python"])
        assert NPMRC_MOUNT_LINE in rebuilt
        assert rebuilt.count("OCF_NPMRC_PATH") == 1

    def test_rebuild_drops_m2_settings_mount_when_maven_removed(self):
        """Disabling Maven strips the settings.xml mirror mount."""
        text = _render_compose(self.REPO, ["java"], java_build_tools=["maven"])
        assert M2_SETTINGS_MOUNT_LINE in text

        rebuilt = self._rebuild(text, ["java"], java_build_tools=["gradle"])
        assert M2_SETTINGS_MOUNT_LINE not in rebuilt


class TestRebuildFeaturesCapsMode:
    """Tests for the docker feature's caps mode in rebuild_features.

    Both modes' managed lines are always stripped, so a mode flip
    reconciles cleanly in either direction and a stale (pre-caps)
    harness converges to caps mode on a rootless outer daemon.
    """

    REPO = "myrepo"

    def test_standard_to_caps_flip(self):
        """Rebuilding a standard harness with podman_caps=True yields the
        caps security block and the /var/lib/containers graph root."""
        text = _render_compose(self.REPO, ["docker"])
        assert "SYS_ADMIN" not in text

        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["docker"], podman_caps=True
        )
        assert "      - SYS_ADMIN" in rebuilt
        assert "      - NET_ADMIN" in rebuilt
        assert f"docker-{self.REPO}-opencode:/var/lib/containers" in rebuilt
        assert (
            f"docker-{self.REPO}-opencode:/home/vscode/.local/share/containers"
            not in rebuilt
        )

    def test_caps_to_standard_flip(self):
        """Rebuilding a caps harness with podman_caps=False yields the
        cap-free security block and the pinned vscode graph root."""
        text = _render_compose_caps(self.REPO, ["docker"])
        assert "SYS_ADMIN" in text

        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["docker"], podman_caps=False
        )
        assert "SYS_ADMIN" not in rebuilt
        assert "NET_ADMIN" not in rebuilt
        assert (
            f"docker-{self.REPO}-opencode:/home/vscode/.local/share/containers"
            in rebuilt
        )
        assert "/var/lib/containers" not in rebuilt

    def test_stale_harness_converges_to_caps(self):
        """A pre-caps harness rebuilt with podman_caps=True converges to
        the exact fresh caps render (byte identity)."""
        stale = _render_compose(self.REPO, ["docker", "python"])
        rebuilt = ComposeGenerator.rebuild_features(
            stale, self.REPO, ["docker", "python"], podman_caps=True
        )
        fresh = _render_compose_caps(self.REPO, ["docker", "python"])
        assert rebuilt == fresh

    def test_stale_harness_converges_to_standard(self):
        """A caps harness rebuilt with podman_caps=False converges to the
        exact fresh standard render (byte identity)."""
        stale = _render_compose_caps(self.REPO, ["docker", "python"])
        rebuilt = ComposeGenerator.rebuild_features(
            stale, self.REPO, ["docker", "python"], podman_caps=False
        )
        fresh = _render_compose(self.REPO, ["docker", "python"])
        assert rebuilt == fresh

    def test_caps_mode_flip_idempotent(self):
        """Applying the same mode twice yields identical output."""
        text = _render_compose(self.REPO, ["docker"])
        once = ComposeGenerator.rebuild_features(
            text, self.REPO, ["docker"], podman_caps=True
        )
        twice = ComposeGenerator.rebuild_features(
            once, self.REPO, ["docker"], podman_caps=True
        )
        assert once == twice

    def test_legacy_remote_user_graph_root_stripped_in_caps_mode(self):
        """The pre-wrapper /home/${REMOTE_USER}/.local/share/containers
        mount is stripped and re-injected at the caps target."""
        legacy_mount = (
            f"      - docker-{self.REPO}-opencode:"
            "/home/${REMOTE_USER}/.local/share/containers"
        )
        text = _render_compose(self.REPO, ["docker"])
        assert legacy_mount not in text
        stale = text.replace(
            f"      - docker-{self.REPO}-opencode:/home/vscode/.local/share/containers",
            legacy_mount,
        )
        rebuilt = ComposeGenerator.rebuild_features(
            stale, self.REPO, ["docker"], podman_caps=True
        )
        assert legacy_mount not in rebuilt
        assert f"docker-{self.REPO}-opencode:/var/lib/containers" in rebuilt

    def test_legacy_dind_stripped_in_caps_mode(self):
        """The legacy DinD /var/lib/docker mount is stripped and the caps
        graph root injected instead."""
        legacy_dind = f"      - docker-{self.REPO}-opencode:/var/lib/docker"
        text = _render_compose(self.REPO, ["docker"])
        stale = text.replace(
            f"      - docker-{self.REPO}-opencode:/home/vscode/.local/share/containers",
            legacy_dind,
        )
        rebuilt = ComposeGenerator.rebuild_features(
            stale, self.REPO, ["docker"], podman_caps=True
        )
        assert legacy_dind not in rebuilt
        assert "privileged" not in rebuilt
        assert f"docker-{self.REPO}-opencode:/var/lib/containers" in rebuilt

    def test_no_docker_feature_caps_mode_uses_base_block(self):
        """Without the docker feature, podman_caps has no effect: the
        base security block is used and no caps appear."""
        text = _render_compose(self.REPO, ["python"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["python"], podman_caps=True
        )
        assert "SYS_ADMIN" not in rebuilt
        assert "seccomp=unconfined" not in rebuilt
        assert "apparmor=unconfined" in rebuilt
        fresh = _render_compose(self.REPO, ["python"])
        assert rebuilt == fresh


class TestDetectPorts:
    """Tests for ComposeGenerator.detect_ports."""

    def test_detects_single_port(self):
        text = _render_compose("repo", [], ["8080:8080"])
        assert ComposeGenerator.detect_ports(text) == ["8080:8080"]

    def test_detects_multiple_ports(self):
        ports = ["8080:8080", "3000:3000", "127.0.0.1:9090:9090"]
        text = _render_compose("repo", [], ports)
        assert ComposeGenerator.detect_ports(text) == ports

    def test_no_ports_returns_empty(self):
        text = _render_compose("repo", [], [])
        assert ComposeGenerator.detect_ports(text) == []

    def test_detect_stops_at_next_key(self):
        text = _render_compose("repo", ["docker"], ["8080:8080"])
        ports = ComposeGenerator.detect_ports(text)
        assert ports == ["8080:8080"]

    def test_detect_protocol_suffix(self):
        text = _render_compose("repo", [], ["8443:443/tcp"])
        assert ComposeGenerator.detect_ports(text) == ["8443:443/tcp"]

    def test_detect_roundtrip_with_rebuild(self):
        """Ports detected from rendered output match what was passed in."""
        ports = ["8080:8080", "3000:3000"]
        text = _render_compose("repo", ["python"], ports)
        rebuilt = ComposeGenerator.rebuild_features(
            text, "repo", ["python"], port_mappings=ports
        )
        assert ComposeGenerator.detect_ports(rebuilt) == ports


class TestRebuildPorts:
    """Tests for port handling in ComposeGenerator.rebuild_features."""

    REPO = "myrepo"

    def test_add_ports_to_empty(self):
        text = _render_compose(self.REPO, [])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, [], port_mappings=["8080:8080"]
        )
        assert "    ports:" in rebuilt
        assert "      - 8080:8080" in rebuilt
        assert ComposeGenerator.detect_ports(rebuilt) == ["8080:8080"]

    def test_remove_ports(self):
        text = _render_compose(self.REPO, [], ["8080:8080"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, [], port_mappings=[]
        )
        assert "ports:" not in rebuilt
        assert ComposeGenerator.detect_ports(rebuilt) == []

    def test_replace_ports(self):
        text = _render_compose(self.REPO, [], ["8080:8080"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, [], port_mappings=["3000:3000", "9090:9090"]
        )
        assert ComposeGenerator.detect_ports(rebuilt) == ["3000:3000", "9090:9090"]
        assert "8080" not in rebuilt

    def test_none_preserves_existing_ports(self):
        """port_mappings=None must leave existing ports untouched."""
        text = _render_compose(self.REPO, [], ["8080:8080"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["python"], port_mappings=None
        )
        assert ComposeGenerator.detect_ports(rebuilt) == ["8080:8080"]

    def test_idempotent(self):
        """Applying the same ports twice yields identical output."""
        ports = ["8080:8080", "3000:3000"]
        text = _render_compose(self.REPO, ["docker"], ports)
        once = ComposeGenerator.rebuild_features(
            text, self.REPO, ["docker"], port_mappings=ports
        )
        twice = ComposeGenerator.rebuild_features(
            once, self.REPO, ["docker"], port_mappings=ports
        )
        assert once == twice

    def test_ports_coexist_with_docker_and_features(self):
        """Ports, docker security, and volume mounts all present together."""
        ports = ["8080:8080"]
        text = _render_compose(self.REPO, [], [])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["python", "docker"], port_mappings=ports
        )
        assert "seccomp=unconfined" in rebuilt
        assert (
            f"venv-{self.REPO}-opencode:${{OCF_LOCAL_REPO_ROOT:-${{PWD}}}}/.venv"
            in rebuilt
        )
        assert ComposeGenerator.detect_ports(rebuilt) == ports

    def test_preserves_manual_env_var_with_ports(self):
        """User-added environment lines survive a port rebuild."""
        text = _render_compose(self.REPO, [])
        text = text.replace(
            "      - XDG_CACHE_HOME=${XDG_CACHE_HOME:-/${REMOTE_USER}/.cache}",
            "      - XDG_CACHE_HOME=${XDG_CACHE_HOME:-/${REMOTE_USER}/.cache}"
            "\n      - MY_CUSTOM=keepme",
            1,
        )
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, [], port_mappings=["8080:8080"]
        )
        assert "MY_CUSTOM=keepme" in rebuilt


class TestRenderComposeTemplateVolumeFix:
    """Regression tests for the java-without-python volumes: header bug."""

    def test_java_only_has_volumes_header(self):
        text = _render_compose("repo", ["java"], java_build_tools=["maven"])
        assert "\nvolumes:" in text
        assert "  m2-repo-opencode:" in text.split("\n")

    def test_java_only_not_orphaned_under_services(self):
        """The m2 volume key must live under top-level volumes:, not services."""
        text = _render_compose("repo", ["java"], java_build_tools=["maven"])
        lines = text.split("\n")
        vol_idx = next(i for i, ln in enumerate(lines) if ln == "volumes:")
        assert lines[vol_idx + 1] == "  m2-repo-opencode:"

    def test_python_and_java_both_volumes(self):
        text = _render_compose("repo", ["python", "java"], java_build_tools=["maven"])
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo-opencode:" in text.split("\n")
        assert "  m2-repo-opencode:" in text.split("\n")

    def test_no_features_no_volumes(self):
        text = _render_compose("repo", [])
        assert "\nvolumes:" not in text

    def test_java_gradle_only_has_gradle_volume(self):
        """Gradle only adds gradle- volume, not m2."""
        text = _render_compose("repo", ["java"], java_build_tools=["gradle"])
        assert "\nvolumes:" in text
        assert "  gradle-repo-opencode:" in text.split("\n")
        assert "  m2-repo-opencode:" not in text.split("\n")

    def test_java_gradle_mounts_gradle_home(self):
        """Gradle only mounts the gradle home directory."""
        text = _render_compose("repo", ["java"], java_build_tools=["gradle"])
        assert "gradle-repo-opencode:/home/${REMOTE_USER}/.gradle" in text
        assert "m2-repo-opencode" not in text

    def test_java_without_tools_no_tool_volumes(self):
        """Java with empty build tools must not silently mount maven volumes."""
        text = _render_compose("repo", ["java"], java_build_tools=[])
        assert "  m2-repo-opencode:" not in text.split("\n")
        assert "  gradle-repo-opencode:" not in text.split("\n")
        assert "m2-repo-opencode:/home" not in text
        assert "gradle-repo-opencode:/home" not in text
        assert "\nvolumes:" not in text

    def test_docker_only_has_volumes_header(self):
        """Podman adds a named volume for its graph root."""
        text = _render_compose("repo", ["docker"])
        assert "\nvolumes:" in text
        assert "  docker-repo-opencode:" in text.split("\n")

    def test_docker_volume_mounts_local_share_containers(self):
        """Podman mount targets the pinned vscode graph root."""
        text = _render_compose("repo", ["docker"])
        assert "docker-repo-opencode:/home/vscode/.local/share/containers" in text

    def test_python_and_docker_both_volumes(self):
        """Python and Podman both add top-level volume keys."""
        text = _render_compose("repo", ["python", "docker"])
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo-opencode:" in text.split("\n")
        assert "  docker-repo-opencode:" in text.split("\n")

    def test_java_docker_and_python_all_volumes(self):
        """All three features add their own volume keys."""
        text = _render_compose(
            "repo", ["python", "java", "docker"], java_build_tools=["maven"]
        )
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo-opencode:" in text.split("\n")
        assert "  m2-repo-opencode:" in text.split("\n")
        assert "  docker-repo-opencode:" in text.split("\n")
        assert "      - m2-repo-opencode:/home/${REMOTE_USER}/.m2" in text

    def test_java_both_has_both_volumes(self):
        """Both Maven and Gradle add both volumes."""
        text = _render_compose("repo", ["java"], java_build_tools=["maven", "gradle"])
        assert "\nvolumes:" in text
        assert "  m2-repo-opencode:" in text.split("\n")
        assert "  gradle-repo-opencode:" in text.split("\n")

    def test_java_both_has_both_mounts(self):
        """Both Maven and Gradle add both service mounts."""
        text = _render_compose("repo", ["java"], java_build_tools=["maven", "gradle"])
        assert "      - m2-repo-opencode:/home/${REMOTE_USER}/.m2" in text
        assert "      - gradle-repo-opencode:/home/${REMOTE_USER}/.gradle" in text


class TestUpdateFeatures:
    """Tests for the high-level features.update_features orchestrator."""

    def _seed_opencode(
        self,
        tmp_path: Path,
        features_list: List[str],
        java_build_tools: List[str] = None,
    ) -> Path:
        """Create a minimal .opencode dir with devcontainer.json + compose.

        devcontainer.json is written in the managed format (indent 2,
        trailing newline) including the Dockerfile initializer the
        current framework version generates, so a no-change
        update_features run is byte-stable.

        Args:
            tmp_path: Temporary path
            features_list: List of feature keys to include
            java_build_tools: Java build tools, e.g. ["maven"], ["gradle"],
                or ["maven", "gradle"]
        """
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        dc = {
            "features": {},
            "initializeCommand": (
                DevcontainerGenerator._build_dockerfile_initializer(
                    "opencode", features_list
                )
            ),
        }
        DevcontainerGenerator._add_optional_features(
            dc["features"], features_list, java_build_tools=java_build_tools
        )
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc, indent=2) + "\n")
        (opencode_dir / "docker-compose.yaml").write_text(
            TemplateHandler.render_compose_template(
                tmp_path.name, features_list, java_build_tools=java_build_tools
            )
        )
        return opencode_dir

    def _forbid_prompts(self, monkeypatch) -> None:
        """Make any prompt call fail the test."""

        def _fail(*args, **kwargs):
            raise AssertionError("prompts must not run non-interactively")

        monkeypatch.setattr(features, "prompt_feature_changes", _fail)
        monkeypatch.setattr(features, "prompt_port_mappings", _fail)

    def test_non_interactive_skips_prompts_but_reconciles(
        self, tmp_path: Path, monkeypatch
    ):
        """Without a TTY, update_features must not prompt — but still
        reconcile: a stale initializer (older framework version,
        echo -e style) is refreshed and the change is reported."""
        monkeypatch.setattr(features, "is_interactive", lambda: False)
        self._forbid_prompts(monkeypatch)
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        compose_before = (opencode_dir / "docker-compose.yaml").read_text()

        # Simulate a harness generated by an older framework version:
        # old-style initializer, non-managed serialization.
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        dc["initializeCommand"] = "echo -e 'stale' > Dockerfile"
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc))

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")

        assert result is True
        refreshed = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "OCF_DOCKERFILE_EOF" in refreshed["initializeCommand"]
        # Compose was already in sync — untouched.
        assert (opencode_dir / "docker-compose.yaml").read_text() == compose_before

    def test_non_interactive_clean_harness_is_noop(self, tmp_path: Path, monkeypatch):
        """Non-TTY over an up-to-date harness: no prompts, no writes."""
        monkeypatch.setattr(features, "is_interactive", lambda: False)
        self._forbid_prompts(monkeypatch)
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()
        compose_before = (opencode_dir / "docker-compose.yaml").read_text()

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")

        assert result is False
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before
        assert (opencode_dir / "docker-compose.yaml").read_text() == compose_before

    def test_same_skips_prompts_on_tty(self, tmp_path: Path, monkeypatch):
        """same=True forces the non-interactive path even on a TTY: no
        prompts, detected selection kept, stale initializer still
        reconciled (mirrors the redirected-stdin behavior)."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        self._forbid_prompts(monkeypatch)
        opencode_dir = self._seed_opencode(tmp_path, ["python"])

        # Simulate a harness generated by an older framework version.
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        dc["initializeCommand"] = "echo -e 'stale' > Dockerfile"
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc))

        result = features.update_features(
            opencode_dir, tmp_path.name, "opencode", same=True
        )

        assert result is True
        refreshed = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "OCF_DOCKERFILE_EOF" in refreshed["initializeCommand"]
        # Feature selection untouched: python still detected as enabled.
        assert DevcontainerGenerator.detect(refreshed) == ["python"]

    def test_non_interactive_reconciles_caps_flip(self, tmp_path: Path, monkeypatch):
        """Non-TTY reconcile still flips compose to caps mode and re-renders
        the caps initializer — a CI reconfigure on a switched daemon must
        not leave a harness that fails launch validation."""
        monkeypatch.setattr(features, "is_interactive", lambda: False)
        self._forbid_prompts(monkeypatch)
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])

        result = features.update_features(
            opencode_dir, tmp_path.name, "opencode", podman_caps=True
        )

        assert result is True
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "mount -o remount,rw /proc/sys" in dc["initializeCommand"]
        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "      - SYS_ADMIN" in compose
        assert f"docker-{tmp_path.name}-opencode:/var/lib/containers" in compose

    def test_legacy_dind_harness_is_migrated(self, tmp_path: Path, monkeypatch):
        """A legacy docker-in-docker harness is reconciled end to end:
        the stale feature key is replaced by the podman packages, the
        old-style initializer is re-rendered with the caps block, and
        the compose converges to caps mode."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        dc = {
            "features": {
                "ghcr.io/devcontainers/features/common-utils:2": {},
                DevcontainerGenerator.LEGACY_DIND_FEATURE_URL: {},
            },
            "build": {"dockerfile": "runtime_data/Dockerfile", "context": "."},
            "initializeCommand": (
                "echo -e 'FROM mcr' > .opencode/runtime_data/Dockerfile"
            ),
        }
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc, indent=2) + "\n")
        (opencode_dir / "docker-compose.yaml").write_text(
            TemplateHandler.render_compose_template(tmp_path.name, ["docker"])
        )

        result = features.update_features(
            opencode_dir, tmp_path.name, "opencode", podman_caps=True
        )
        assert result is True

        migrated = json.loads((opencode_dir / "devcontainer.json").read_text())
        features_map = migrated["features"]
        assert DevcontainerGenerator.LEGACY_DIND_FEATURE_URL not in features_map
        packages = features_map[DevcontainerGenerator.APT_PACKAGES_FEATURE_URL][
            "packages"
        ]
        assert "podman" in packages.split(",")
        # The initializer is re-rendered from current code: heredoc style
        # with the caps block (cgroups conf baked, storage auto-detected).
        initialize = migrated["initializeCommand"]
        assert "OCF_DOCKERFILE_EOF" in initialize
        assert "echo -e" not in initialize
        assert "'cgroups = \"disabled\"'" in initialize
        assert 'driver = "vfs"' not in initialize
        assert "mount -o remount,rw /proc/sys" in initialize
        # Untouched keys survive the surgical write.
        assert migrated["build"] == {
            "dockerfile": "runtime_data/Dockerfile",
            "context": ".",
        }
        # Compose reconciled to caps mode.
        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "      - SYS_ADMIN" in compose
        assert f"docker-{tmp_path.name}-opencode:/var/lib/containers" in compose

    def test_update_features_idempotent(self, tmp_path: Path, monkeypatch):
        """A second reconcile run over an already-reconciled harness
        changes nothing (byte-stable)."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])

        # First run flips to caps mode: initializer + compose reconciled.
        assert (
            features.update_features(
                opencode_dir, tmp_path.name, "opencode", podman_caps=True
            )
            is True
        )
        dc_after = (opencode_dir / "devcontainer.json").read_text()
        compose_after = (opencode_dir / "docker-compose.yaml").read_text()

        result = features.update_features(
            opencode_dir, tmp_path.name, "opencode", podman_caps=True
        )

        assert result is False
        assert (opencode_dir / "devcontainer.json").read_text() == dc_after
        assert (opencode_dir / "docker-compose.yaml").read_text() == compose_after

    def test_unreadable_devcontainer_returns_false(self, tmp_path: Path, monkeypatch):
        """A broken devcontainer.json should not crash, just skip."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{ not valid json")

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is False

    def test_no_change_returns_false(self, tmp_path: Path, monkeypatch):
        """When the user keeps the same selection, nothing is written.

        The compose IS reconciled (always now), and devcontainer.json is
        rewritten whenever its serialized content differs (features,
        legacy migration, initializer drift). A clean harness with the
        current initializer yields no diff, so nothing is written and
        False is returned.
        """
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        # Freshly rendered compose is reconcile-clean, so nothing is written
        assert result is False
        # Devcontainer.json is only updated when features change, so it stays unchanged
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before

    def test_change_writes_both_files(self, tmp_path: Path, monkeypatch):
        """A feature change must update devcontainer.json and compose."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        # Simulate the user adding docker + java (maven) to a python setup.
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (["python", "docker", "java"], ["maven"]),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        opencode_dir = self._seed_opencode(tmp_path, ["python"])

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is True

        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected = DevcontainerGenerator.detect(dc)
        assert set(detected) == {"python", "docker", "java"}

        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "seccomp=unconfined" in compose
        assert f"m2-{tmp_path.name}-opencode:/home" in compose

    def test_change_without_compose_only_updates_devcontainer(
        self, tmp_path: Path, monkeypatch
    ):
        """If docker-compose.yaml is absent, only devcontainer.json is updated."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (["python"], []),
        )
        opencode_dir = self._seed_opencode(tmp_path, [])
        (opencode_dir / "docker-compose.yaml").unlink()

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is True
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected = DevcontainerGenerator.detect(dc)
        assert detected == ["python"]

    def test_port_only_change_writes_compose(self, tmp_path: Path, monkeypatch):
        """A port-only change (features unchanged) updates compose but not
        devcontainer."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(
            features, "prompt_port_mappings", lambda cur=None: ["8080:8080"]
        )
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is True
        # devcontainer unchanged (features didn't change)
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before
        # compose now has ports
        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "      - 8080:8080" in compose

    def test_update_features_java_build_tools_roundtrip(
        self, tmp_path: Path, monkeypatch
    ):
        """Java→Gradle transition through update_features must work correctly."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)

        # Seed with java (no explicit build flags in _seed_opencode)
        opencode_dir = self._seed_opencode(tmp_path, ["java"])

        # Monkeypatch prompt to change java build tools to gradle
        def mock_prompt(cur, jbt):
            # Keep java enabled, change build tools
            if "java" in cur:
                jbt = ["gradle"]
            return (list(cur), jbt)

        monkeypatch.setattr(features, "prompt_feature_changes", mock_prompt)
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is True

        # Verify devcontainer.json has installGradle:True, installMaven:False
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        assert dc["features"][java_url]["installMaven"] is False
        assert dc["features"][java_url]["installGradle"] is True

        # Verify compose has gradle- volume, no m2- volume
        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "      - gradle-" in compose
        assert "m2-" not in compose or "      - m2-" not in compose.split("\n")[-5:]
        assert "  gradle-" in compose
        assert "  m2-" not in compose

    def test_update_features_detect_build_tools_no_crash(self, tmp_path: Path):
        """update_features must correctly detect and use build tools from
        devcontainer.json."""
        opencode_dir = self._seed_opencode(tmp_path, ["java"])

        # Call update_features with a no-op prompt (same state)
        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is False  # No changes detected

        # Verify no crash occurred
        dc = (opencode_dir / "devcontainer.json").read_text()
        assert "java" in dc

    def test_no_change_reconciles_drifted_compose(self, tmp_path: Path, monkeypatch):
        """A drifted compose (missing docker volume) gets reconciled even
        with no selection change."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])
        compose_before = (opencode_dir / "docker-compose.yaml").read_text()

        # Manually create a drifted compose without the docker volume
        drifted = compose_before.replace(
            f"      - docker-{tmp_path.name}-opencode:"
            "/home/vscode/.local/share/containers",
            "",
        )
        (opencode_dir / "docker-compose.yaml").write_text(drifted)

        # Monkeypatch prompt to return the same state (no user change)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        # With the fix, compose is always reconciled. Since it drifted,
        # it will be written.
        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is True  # Compose drifted and was reconciled

        # Verify compose is now reconciled - the docker volume is restored
        compose_after = (opencode_dir / "docker-compose.yaml").read_text()
        assert ".local/share/containers" in compose_after
        assert f"docker-{tmp_path.name}-opencode" in compose_after
        assert "seccomp=unconfined" in compose_after

    def test_no_change_in_sync_compose_untouched(self, tmp_path: Path, monkeypatch):
        """When compose is already in sync, no meaningful rewrite occurs
        on no-op --rebuild."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])

        # Monkeypatch prompt to return the same state (no user change)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (list(cur), list(jbt or [])),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        # When compose is already in sync, rebuild_features produces the same
        # bytes → the file is not written → result is False.
        result = features.update_features(opencode_dir, tmp_path.name, "opencode")
        assert result is False

        # Verify compose is unchanged and still valid
        compose_after = (opencode_dir / "docker-compose.yaml").read_text()
        assert "seccomp=unconfined" in compose_after
        assert ".local/share/containers" in compose_after
        assert '["opencode"]' in compose_after

    def test_env_reconciled_during_update(self, tmp_path: Path, monkeypatch):
        """update_features refreshes the feature-dependent .env entries."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (["java"], ["gradle"]),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "/home/alice/.npmrc")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        opencode_dir = self._seed_opencode(tmp_path, [])
        env_path = opencode_dir / ".env"
        env_path.write_text("OCF_AGENT_TOOL=opencode\n")

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")

        assert result is True
        content = env_path.read_text()
        assert "OCF_NPMRC_PATH=/home/alice/.npmrc" in content
        assert "OCF_M2_SETTINGS_PATH=\n" in content
        assert GRADLE_OPTS_LINE in content
        assert "OCF_AGENT_TOOL=opencode" in content

    def test_ssh_toggle_updates_devcontainer_compose_and_env(
        self, tmp_path: Path, monkeypatch
    ):
        """Enabling ssh end to end: openssh-client lands in apt-packages,
        the compose gains the ~/.ssh mirror, .env records the host dir."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, jbt: (["python", "ssh"], []),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(
            features, "host_ssh_dir_path", lambda e: "/home/alice/.ssh" if e else ""
        )
        monkeypatch.setattr(
            "opencode_framework.sandbox.compose.host_ssh_dir_path",
            lambda enabled: "/home/alice/.ssh" if enabled else "",
        )
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        env_path = opencode_dir / ".env"
        env_path.write_text("OCF_AGENT_TOOL=opencode\n")

        result = features.update_features(opencode_dir, tmp_path.name, "opencode")

        assert result is True
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        entry = dc["features"][DevcontainerGenerator.APT_PACKAGES_FEATURE_URL]
        assert "openssh-client" in entry["packages"].split(",")
        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert SSH_MOUNT_LINE in compose
        assert "OCF_SSH_DIR_PATH=/home/alice/.ssh" in env_path.read_text()


class TestMigrateLegacyDind:
    """Tests for DevcontainerGenerator.migrate_legacy_dind."""

    def test_noop_when_key_absent(self):
        """A harness without the legacy key is left untouched."""
        dev = {"features": {"ghcr.io/devcontainers/features/git:1": {}}}
        assert DevcontainerGenerator.migrate_legacy_dind(dev, ["docker"]) is False
        assert dev == {"features": {"ghcr.io/devcontainers/features/git:1": {}}}

    def test_migrates_and_merges_podman_when_docker_active(self):
        """The legacy key is removed and the podman packages merged when
        docker stays active."""
        dev = {"features": {DevcontainerGenerator.LEGACY_DIND_FEATURE_URL: {}}}
        assert DevcontainerGenerator.migrate_legacy_dind(dev, ["docker"]) is True
        assert DevcontainerGenerator.LEGACY_DIND_FEATURE_URL not in dev["features"]
        entry = dev["features"][DevcontainerGenerator.APT_PACKAGES_FEATURE_URL]
        assert "podman" in entry["packages"].split(",")

    def test_removes_key_without_packages_when_docker_deselected(self):
        """With docker deselected the key still goes, but no podman
        packages are merged."""
        dev = {"features": {DevcontainerGenerator.LEGACY_DIND_FEATURE_URL: {}}}
        assert DevcontainerGenerator.migrate_legacy_dind(dev, []) is True
        assert dev["features"] == {}


class TestPromptJavaBuildTools:
    """Unit tests for _prompt_java_build_tools."""

    @pytest.fixture(autouse=True)
    def setup_typer(self, monkeypatch):
        """Mock typer.confirm and typer.echo for testing."""

        class _FakeConfirm:
            def __init__(self):
                self.answers = []
                self.call_count = 0

            def __call__(self, msg, default=False):
                self.call_count += 1
                self.answers.append((msg, default))
                return default

        self.typer_confirm = _FakeConfirm()
        monkeypatch.setattr(
            "opencode_framework.sandbox.features.typer.confirm", self.typer_confirm
        )

        monkeypatch.setattr(
            "opencode_framework.sandbox.features.typer.echo",
            lambda *args, **kwargs: None,
        )

    def test_none_defaults_both_prompts_false(self):
        """When current_tools is None, both prompts default to No."""
        tools = features._prompt_java_build_tools(None)

        assert self.typer_confirm.call_count == 2
        assert self.typer_confirm.answers[0][1] is False
        assert self.typer_confirm.answers[1][1] is False
        assert tools == []

    def test_empty_list_defaults_both_prompts_false(self):
        """When current_tools is [], both prompts default to No."""
        tools = features._prompt_java_build_tools([])

        assert self.typer_confirm.call_count == 2
        assert self.typer_confirm.answers[0][1] is False
        assert self.typer_confirm.answers[1][1] is False
        assert tools == []

    def test_existing_gradle_preserved_as_default(self):
        """When current_tools has gradle, gradle defaults True, maven defaults False."""
        tools = features._prompt_java_build_tools(["gradle"])

        assert self.typer_confirm.call_count == 2
        # First call: default from ["gradle"] means gradle=True, maven=False
        # Second call: repeats previous answer
        assert tools == ["gradle"]

    def test_returns_both_when_both_confirmed(self, monkeypatch):
        """When both maven and gradle confirmed, return both."""
        # Need to mock typer.confirm to return True both times
        with monkeypatch.context() as m:
            call_count = 0

            def mock_confirm(msg, default=False):
                nonlocal call_count
                call_count += 1
                return True  # Always confirm both

            m.setattr("opencode_framework.sandbox.features.typer.confirm", mock_confirm)
            m.setattr(
                "opencode_framework.sandbox.features.typer.echo",
                lambda *args, **kwargs: None,
            )

            tools = features._prompt_java_build_tools([])

            assert call_count == 2
            assert tools == ["maven", "gradle"]


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


class TestParsePortMappings:
    """Tests for features.parse_port_mappings."""

    def test_single_port(self):
        assert features.parse_port_mappings("8080:8080") == ["8080:8080"]

    def test_multiple_ports(self):
        assert features.parse_port_mappings("8080:8080, 3000:3000") == [
            "8080:8080",
            "3000:3000",
        ]

    def test_strips_whitespace(self):
        assert features.parse_port_mappings("  8080:8080  ,  3000  ") == [
            "8080:8080",
            "3000",
        ]

    def test_empty_string(self):
        assert features.parse_port_mappings("") == []

    def test_blank_entries_dropped(self):
        assert features.parse_port_mappings("8080:8080, , ,3000:3000") == [
            "8080:8080",
            "3000:3000",
        ]

    def test_protocol_suffix_preserved(self):
        assert features.parse_port_mappings("8443:443/tcp") == ["8443:443/tcp"]


class TestReconcileEnvForFeatures:
    """Tests for features.reconcile_env_for_features."""

    BASE_ENV = (
        "REMOTE_USER=root\n"
        "OCF_LOCAL_FRAMEWORK_PATH=/opt/framework\n"
        "OCF_REMOTE_FRAMEWORK_CONFIG_PATH=/opt/ocframework/config\n"
        "OCF_NPMRC_PATH=\n"
        "OCF_M2_SETTINGS_PATH=\n"
        "OCF_GITCONFIG_PATH=\n"
        "OCF_SSH_DIR_PATH=\n"
        "OCF_AGENT_TOOL=opencode\n"
        "OCF_MAIN_MODEL=anthropic/claude-opus-4-8\n"
    )

    def _seed(self, tmp_path: Path, text: str = None) -> Path:
        env_path = tmp_path / ".env"
        env_path.write_text(text or self.BASE_ENV)
        return env_path

    def test_no_change_returns_false(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(tmp_path)

        assert features.reconcile_env_for_features(env_path, []) is False
        assert env_path.read_text() == self.BASE_ENV

    def test_sets_mirror_paths_from_host_state(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "/home/alice/.npmrc")
        monkeypatch.setattr(
            features,
            "host_m2_settings_path",
            lambda m: "/home/alice/.m2/settings.xml" if m else "",
        )
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(tmp_path)

        assert features.reconcile_env_for_features(env_path, ["maven"]) is True
        content = env_path.read_text()
        assert "OCF_NPMRC_PATH=/home/alice/.npmrc" in content
        assert "OCF_M2_SETTINGS_PATH=/home/alice/.m2/settings.xml" in content
        # unrelated lines survive
        assert "OCF_MAIN_MODEL=anthropic/claude-opus-4-8" in content

    def test_clears_stale_mirror_paths(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(
            tmp_path,
            self.BASE_ENV.replace(
                "OCF_NPMRC_PATH=", "OCF_NPMRC_PATH=/home/alice/.npmrc\n#dup\n"
            ).replace(
                "OCF_M2_SETTINGS_PATH=",
                "OCF_M2_SETTINGS_PATH=/home/alice/.m2/settings.xml",
            ),
        )

        assert features.reconcile_env_for_features(env_path, []) is True
        content = env_path.read_text()
        assert "OCF_NPMRC_PATH=\n" in content
        assert "/home/alice/.npmrc" not in content
        assert "OCF_M2_SETTINGS_PATH=\n" in content

    def test_m2_settings_cleared_when_maven_deselected(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(
            features,
            "host_m2_settings_path",
            lambda m: "/home/alice/.m2/settings.xml" if m else "",
        )
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(
            tmp_path,
            self.BASE_ENV.replace(
                "OCF_M2_SETTINGS_PATH=",
                "OCF_M2_SETTINGS_PATH=/home/alice/.m2/settings.xml",
            ),
        )

        assert features.reconcile_env_for_features(env_path, ["gradle"]) is True
        assert "OCF_M2_SETTINGS_PATH=\n" in env_path.read_text()

    def test_adds_gradle_opts_when_selected(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(tmp_path)

        assert features.reconcile_env_for_features(env_path, ["gradle"]) is True
        content = env_path.read_text()
        assert f"{GRADLE_ENV_COMMENT}\n{GRADLE_OPTS_LINE}" in content

    def test_gradle_line_idempotent_when_already_present(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        seed = self.BASE_ENV.replace(
            "OCF_AGENT_TOOL=opencode",
            f"{GRADLE_ENV_COMMENT}\n{GRADLE_OPTS_LINE}\nOCF_AGENT_TOOL=opencode",
        )
        env_path = self._seed(tmp_path, seed)

        assert features.reconcile_env_for_features(env_path, ["gradle"]) is False

    def test_gradle_line_removed_when_deselected(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        seed = self.BASE_ENV.replace(
            "OCF_AGENT_TOOL=opencode",
            f"{GRADLE_ENV_COMMENT}\n{GRADLE_OPTS_LINE}\nOCF_AGENT_TOOL=opencode",
        )
        env_path = self._seed(tmp_path, seed)

        assert features.reconcile_env_for_features(env_path, []) is True
        content = env_path.read_text()
        assert "GRADLE_OPTS" not in content
        assert GRADLE_ENV_COMMENT not in content

    def test_pinned_over_custom_value_when_gradle_selected(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        seed = self.BASE_ENV.replace(
            "OCF_AGENT_TOOL=opencode",
            'GRADLE_OPTS="-Xmx1g"\nOCF_AGENT_TOOL=opencode',
        )
        env_path = self._seed(tmp_path, seed)

        assert features.reconcile_env_for_features(env_path, ["gradle"]) is True
        content = env_path.read_text()
        assert GRADLE_OPTS_LINE in content
        assert "-Xmx1g" not in content

    def test_custom_gradle_opts_survive_deselection(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        seed = self.BASE_ENV.replace(
            "OCF_AGENT_TOOL=opencode",
            'GRADLE_OPTS="-Xmx1g"\nOCF_AGENT_TOOL=opencode',
        )
        env_path = self._seed(tmp_path, seed)

        assert features.reconcile_env_for_features(env_path, []) is False
        assert 'GRADLE_OPTS="-Xmx1g"' in env_path.read_text()

    def test_inserts_missing_keys_after_anchors(self, tmp_path: Path, monkeypatch):
        """Legacy .env files without the mirror keys gain them in place."""
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "/home/alice/.npmrc")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        legacy = (
            "REMOTE_USER=root\n"
            "OCF_LOCAL_FRAMEWORK_PATH=/opt/framework\n"
            "OCF_REMOTE_FRAMEWORK_CONFIG_PATH=/opt/ocframework/config\n"
            "OCF_AGENT_TOOL=opencode\n"
        )
        env_path = self._seed(tmp_path, legacy)

        assert features.reconcile_env_for_features(env_path, ["gradle"]) is True
        content = env_path.read_text()
        assert "OCF_NPMRC_PATH=/home/alice/.npmrc" in content
        assert "OCF_M2_SETTINGS_PATH=" in content
        assert GRADLE_OPTS_LINE in content
        lines = content.split("\n")
        npmrc_idx = lines.index("OCF_NPMRC_PATH=/home/alice/.npmrc")
        m2_idx = lines.index("OCF_M2_SETTINGS_PATH=")
        gradle_idx = lines.index(GRADLE_OPTS_LINE)
        assert npmrc_idx < m2_idx < gradle_idx

    def test_gitconfig_refreshed_from_host_state(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(
            features, "host_gitconfig_path", lambda: "/home/alice/.gitconfig"
        )
        monkeypatch.setattr(features, "host_ssh_dir_path", lambda _: "")
        env_path = self._seed(
            tmp_path,
            self.BASE_ENV.replace(
                "OCF_GITCONFIG_PATH=", "OCF_GITCONFIG_PATH=/stale/path"
            ),
        )

        assert features.reconcile_env_for_features(env_path, []) is True
        content = env_path.read_text()
        assert "OCF_GITCONFIG_PATH=/home/alice/.gitconfig\n" in content
        assert "/stale/path" not in content

    def test_ssh_dir_set_and_cleared_with_feature_flag(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(features, "host_gitconfig_path", lambda: "")
        monkeypatch.setattr(
            features, "host_ssh_dir_path", lambda e: "/home/alice/.ssh" if e else ""
        )
        env_path = self._seed(
            tmp_path,
            self.BASE_ENV.replace(
                "OCF_SSH_DIR_PATH=", "OCF_SSH_DIR_PATH=/home/alice/.ssh"
            ),
        )

        assert features.reconcile_env_for_features(env_path, [], ssh_enabled=True) is (
            False
        )
        assert (
            features.reconcile_env_for_features(env_path, [], ssh_enabled=False) is True
        )
        assert "OCF_SSH_DIR_PATH=\n" in env_path.read_text()

    def test_inserts_gitconfig_and_ssh_after_anchor_chain(
        self, tmp_path: Path, monkeypatch
    ):
        """Legacy .env gains gitconfig/ssh keys in template order, past
        the gradle block when present."""
        monkeypatch.setattr(features, "host_npmrc_path", lambda: "")
        monkeypatch.setattr(features, "host_m2_settings_path", lambda _: "")
        monkeypatch.setattr(
            features, "host_gitconfig_path", lambda: "/home/alice/.gitconfig"
        )
        monkeypatch.setattr(
            features, "host_ssh_dir_path", lambda e: "/home/alice/.ssh" if e else ""
        )
        legacy = (
            "REMOTE_USER=root\n"
            "OCF_LOCAL_FRAMEWORK_PATH=/opt/framework\n"
            "OCF_REMOTE_FRAMEWORK_CONFIG_PATH=/opt/ocframework/config\n"
            "OCF_AGENT_TOOL=opencode\n"
        )
        env_path = self._seed(tmp_path, legacy)

        assert (
            features.reconcile_env_for_features(env_path, ["gradle"], ssh_enabled=True)
            is True
        )
        lines = env_path.read_text().split("\n")
        npmrc_idx = lines.index("OCF_NPMRC_PATH=")
        m2_idx = lines.index("OCF_M2_SETTINGS_PATH=")
        gradle_idx = lines.index(GRADLE_OPTS_LINE)
        gitconfig_idx = lines.index("OCF_GITCONFIG_PATH=/home/alice/.gitconfig")
        ssh_idx = lines.index("OCF_SSH_DIR_PATH=/home/alice/.ssh")
        assert npmrc_idx < m2_idx < gradle_idx < gitconfig_idx < ssh_idx
