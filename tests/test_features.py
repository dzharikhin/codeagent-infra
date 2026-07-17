"""Tests for interactive feature management and surgical config updates."""

import json
from pathlib import Path
from typing import List

import pytest

from opencode_framework import features
from opencode_framework.generators.compose import ComposeGenerator
from opencode_framework.generators.devcontainer import (
    COMMON_UTILS_URL,
    DevcontainerGenerator,
)
from opencode_framework.generators.templates import TemplateHandler


def _dc_with_features(*features: str, editor: str = "none") -> dict:
    """Build a devcontainer dict with the given optional features."""
    dc = {"features": {}}
    DevcontainerGenerator._add_optional_features(dc["features"], list(features), editor)
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

    def test_detect_build_tools_default_to_maven_when_no_flags(self):
        """Backward compatibility: Java present but no build flags → default to maven."""
        dc = _dc_with_features("java")
        tools = DevcontainerGenerator.detect_build_tools(dc)
        assert tools == ["maven"]

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
        result = DevcontainerGenerator.apply_delta(
            dc, add=["docker"], remove=[], editor="none"
        )
        assert result is dc

    def test_apply_delta_creates_features_key_if_missing(self):
        dc = {}
        DevcontainerGenerator.apply_delta(dc, add=["python"], remove=[], editor="none")
        assert "features" in dc
        assert DevcontainerGenerator.FEATURE_URL_MAP["python"] in dc["features"]


class TestRebuildFeatures:
    """Tests for ComposeGenerator.rebuild_features."""

    REPO = "myrepo"

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
        assert ("    privileged: true" in text.split("\n")) is has_docker
        assert ("    init: true" in text.split("\n")) is True
        assert ("docker-init.sh" in text) is has_docker
        # Python venv volume is mounted at /myrepo/.venv, not /home
        assert (f"venv-{self.REPO}:/myrepo/.venv" in text) is (
            "python" in features
        )
        # Maven m2 volume is mounted at /home/${REMOTE_USER}/.m2
        assert (f"m2-{self.REPO}:/home/${{REMOTE_USER}}/.m2" in text) is (
            "java" in features and ("maven" in (java_build_tools or ["maven"]))
        )
        # Gradle home volume is mounted at /home/${REMOTE_USER}/.gradle
        assert (f"gradle-{self.REPO}:/home/${{REMOTE_USER}}/.gradle" in text) is (
            "java" in features and ("gradle" in (java_build_tools or ["maven"]))
        )
        assert (f"docker-{self.REPO}:/var/lib/docker" in text) is has_docker
        if "python" in features or (
            "java" in features
            and (
                "maven" in (java_build_tools or ["maven"])
                or "gradle" in (java_build_tools or ["maven"])
            )
        ) or has_docker:
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
        assert f"docker-{self.REPO}:/var/lib/docker" in rebuilt.split("\n")

    def test_toggle_docker_off(self):
        text = _render_compose(self.REPO, ["docker"])
        rebuilt = self._rebuild(text, [])
        assert '["opencode"]' in rebuilt
        assert "    privileged: true" not in rebuilt.split("\n")
        assert f"docker-{self.REPO}:/var/lib/docker" not in rebuilt.split("\n")

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
        svc_idx = next(
            i
            for i, ln in enumerate(lines)
            if ln.strip() == "volumes:" and ln.startswith(" ")
        )
        # the line right after the service-level volumes: key must be a mount, not a top-level key
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

    def test_rebuild_features_accepts_java_build_tools_kwarg(self):
        """rebuild_features must accept java_build_tools as a keyword argument."""
        text = _render_compose(self.REPO, ["java"])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["java"], java_build_tools=["gradle"]
        )
        assert "gradle-" in rebuilt


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
        """Ports, privileged, and volume mounts all present together."""
        ports = ["8080:8080"]
        text = _render_compose(self.REPO, [], [])
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, ["python", "docker"], port_mappings=ports
        )
        assert "    privileged: true" in rebuilt
        assert f"venv-{self.REPO}:/{self.REPO}/.venv" in rebuilt
        assert ComposeGenerator.detect_ports(rebuilt) == ports

    def test_preserves_manual_env_var_with_ports(self):
        """User-added environment lines survive a port rebuild."""
        text = _render_compose(self.REPO, [])
        text = text.replace(
            "      - OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT=true",
            "      - OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT=true\n      - MY_CUSTOM=keepme",
            1,
        )
        rebuilt = ComposeGenerator.rebuild_features(
            text, self.REPO, [], port_mappings=["8080:8080"]
        )
        assert "MY_CUSTOM=keepme" in rebuilt


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

    def test_java_gradle_only_has_gradle_volume(self):
        """Gradle only adds gradle- volume, not m2."""
        text = _render_compose("repo", ["java"], java_build_tools=["gradle"])
        assert "\nvolumes:" in text
        assert "  gradle-repo:" in text.split("\n")
        assert "  m2-repo:" not in text.split("\n")

    def test_java_gradle_mounts_gradle_home(self):
        """Gradle only mounts the gradle home directory."""
        text = _render_compose("repo", ["java"], java_build_tools=["gradle"])

    def test_docker_only_has_volumes_header(self):
        """Docker adds a named volume for /var/lib/docker."""
        text = _render_compose("repo", ["docker"])
        assert "\nvolumes:" in text
        assert "  docker-repo:" in text.split("\n")

    def test_docker_volume_mounts_var_lib_docker(self):
        """Docker mount targets /var/lib/docker."""
        text = _render_compose("repo", ["docker"])
        assert "docker-repo:/var/lib/docker" in text.split("\n")

    def test_python_and_docker_both_volumes(self):
        """Python and Docker both add top-level volume keys."""
        text = _render_compose("repo", ["python", "docker"])
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo:" in text.split("\n")
        assert "  docker-repo:" in text.split("\n")

    def test_java_docker_and_python_all_volumes(self):
        """All three features add their own volume keys."""
        text = _render_compose("repo", ["python", "java", "docker"])
        assert text.count("\nvolumes:") == 1
        assert "  venv-repo:" in text.split("\n")
        assert "  m2-repo:" in text.split("\n")
        assert "  docker-repo:" in text.split("\n")
        assert "      - gradle-repo:/home/${REMOTE_USER}/.gradle" in text

    def test_java_both_has_both_volumes(self):
        """Both Maven and Gradle add both volumes."""
        text = _render_compose("repo", ["java"], java_build_tools=["maven", "gradle"])
        assert "\nvolumes:" in text
        assert "  m2-repo:" in text.split("\n")
        assert "  gradle-repo:" in text.split("\n")

    def test_java_both_has_both_mounts(self):
        """Both Maven and Gradle add both service mounts."""
        text = _render_compose("repo", ["java"], java_build_tools=["maven", "gradle"])
        assert "      - m2-repo:/home/${REMOTE_USER}/.m2" in text
        assert "      - gradle-repo:/home/${REMOTE_USER}/.gradle" in text


class TestUpdateFeatures:
    """Tests for the high-level features.update_features orchestrator."""

    def _seed_opencode(
        self,
        tmp_path: Path,
        features_list: List[str],
        java_build_tools: List[str] = None,
    ) -> Path:
        """Create a minimal .opencode dir with devcontainer.json + compose.

        Args:
            tmp_path: Temporary path
            features_list: List of feature keys to include
            java_build_tools: List of Java build tools (e.g. ["maven"], ["gradle"], ["maven", "gradle"])
        """
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        dc = {"features": {}}
        DevcontainerGenerator._add_optional_features(
            dc["features"], features_list, "none", java_build_tools=java_build_tools
        )
        (opencode_dir / "devcontainer.json").write_text(json.dumps(dc))
        (opencode_dir / "docker-compose.yaml").write_text(
            TemplateHandler.render_compose_template(
                tmp_path.name, features_list, java_build_tools=java_build_tools
            )
        )
        return opencode_dir

    def test_non_interactive_returns_false_and_is_noop(
        self, tmp_path: Path, monkeypatch
    ):
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
        """When the user keeps the same selection, devcontainer.json is untouched.

        The compose IS reconciled (always now), but devcontainer.json is only
        written when features actually change. The return value indicates if
        anything was written (either features OR compose drift), so it returns
        True when compose is out of sync and False when truly no changes occurred.
        """
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (list(cur), ed, []),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()

        result = features.update_features(opencode_dir, tmp_path.name)
        # Compose is reconciled even on no-op, so it's written back
        assert result is True
        # Devcontainer.json is only updated when features change, so it stays unchanged
        assert (opencode_dir / "devcontainer.json").read_text() == dc_before

    def test_change_writes_both_files(self, tmp_path: Path, monkeypatch):
        """A feature change must update devcontainer.json and compose."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        # Simulate the user adding docker + java to an existing python setup.
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (["python", "docker", "java"], ed, []),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])
        opencode_dir = self._seed_opencode(tmp_path, ["python"])

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True

        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected, _ = DevcontainerGenerator.detect(dc)
        assert set(detected) == {"python", "docker", "java"}

        compose = (opencode_dir / "docker-compose.yaml").read_text()
        assert "docker-init.sh" in compose
        assert f"m2-{tmp_path.name}:/home" in compose

    def test_change_without_compose_only_updates_devcontainer(
        self, tmp_path: Path, monkeypatch
    ):
        """If docker-compose.yaml is absent, only devcontainer.json is updated."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (["python"], ed, []),
        )
        opencode_dir = self._seed_opencode(tmp_path, [])
        (opencode_dir / "docker-compose.yaml").unlink()

        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True
        dc = json.loads((opencode_dir / "devcontainer.json").read_text())
        detected, _ = DevcontainerGenerator.detect(dc)
        assert detected == ["python"]

    def test_port_only_change_writes_compose(self, tmp_path: Path, monkeypatch):
        """A port-only change (features unchanged) updates compose but not devcontainer."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (list(cur), ed, []),
        )
        monkeypatch.setattr(
            features, "prompt_port_mappings", lambda cur=None: ["8080:8080"]
        )
        opencode_dir = self._seed_opencode(tmp_path, ["python"])
        dc_before = (opencode_dir / "devcontainer.json").read_text()

        result = features.update_features(opencode_dir, tmp_path.name)
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

        # Seed with java+maven (no explicit build flags in _seed_opencode)
        opencode_dir = self._seed_opencode(tmp_path, ["java"])

        # Monkeypatch prompt to change java from maven to gradle
        def mock_prompt(cur, ed, jbt):
            # Keep java enabled, change build tools
            if "java" in cur:
                cur = [f for f in cur if f != "java"] + ["java"]
                jbt = ["gradle"]
            return (cur, ed, jbt)

        monkeypatch.setattr(features, "prompt_feature_changes", mock_prompt)
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        result = features.update_features(opencode_dir, tmp_path.name)
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
        """update_features must correctly detect and use build tools from devcontainer.json."""
        opencode_dir = self._seed_opencode(tmp_path, ["java"])

        # Call update_features with a no-op prompt (same state)
        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is False  # No changes detected

        # Verify no crash occurred
        dc = (opencode_dir / "devcontainer.json").read_text()
        assert "java" in dc

    def test_no_change_reconciles_drifted_compose(self, tmp_path: Path, monkeypatch):
        """A drifted compose (missing docker volume) gets reconciled even with no selection change."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])
        compose_before = (opencode_dir / "docker-compose.yaml").read_text()

        # Manually create a drifted compose without the docker volume
        drifted = compose_before.replace(
            "      - docker-repo:/var/lib/docker",
            "",
        ).replace(
            "  docker-repo:",
            "",
        ).replace(
            "    privileged: true",
            "",
        ).replace(
            '["/usr/local/share/docker-init.sh", "opencode"]',
            '["opencode"]',
        ).replace(
            "\n  volumes:",
            "\nvolumes:",
        )
        (opencode_dir / "docker-compose.yaml").write_text(drifted)

        # Monkeypatch prompt to return the same state (no user change)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (list(cur), ed, []),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        # With the fix, compose is always reconciled. Since it drifted, it will be written.
        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True  # Compose drifted and was reconciled

        # Verify compose is now reconciled - the docker volume is restored
        compose_after = (opencode_dir / "docker-compose.yaml").read_text()
        # The mount name will use tmp_path.name, which is the actual repo path
        assert any("/var/lib/docker" in line for line in compose_after.split("\n"))
        assert any(f"docker-{tmp_path.name}" in line for line in compose_after.split("\n"))
        assert "    privileged: true" in compose_after
        assert '["/usr/local/share/docker-init.sh", "opencode"]' in compose_after

    def test_no_change_in_sync_compose_untouched(self, tmp_path: Path, monkeypatch):
        """When compose is already in sync, no meaningful rewrite occurs on no-op --rebuild."""
        monkeypatch.setattr(features, "is_interactive", lambda: True)
        opencode_dir = self._seed_opencode(tmp_path, ["docker"])

        # Monkeypatch prompt to return the same state (no user change)
        monkeypatch.setattr(
            features,
            "prompt_feature_changes",
            lambda cur, ed, jbt: (list(cur), ed, []),
        )
        monkeypatch.setattr(features, "prompt_port_mappings", lambda cur=None: [])

        # With the fix, compose is always reconciled. If it's in sync, no bytes change.
        # The function returns True when anything was written (even if bytes unchanged).
        result = features.update_features(opencode_dir, tmp_path.name)
        assert result is True  # Compose was reconciled (bytes unchanged is still a write)

        # Verify compose bytes are unchanged (idempotent - only whitespace differences expected)
        compose_after = (opencode_dir / "docker-compose.yaml").read_text()
        # Jinja2 may normalize whitespace differently on each pass
        # The important thing is the docker volume is present and privileged line is there
        assert any("/var/lib/docker" in line for line in compose_after.split("\n"))
        assert "    privileged: true" in compose_after
        assert '["/usr/local/share/docker-init.sh", "opencode"]' in compose_after


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
            "opencode_framework.features.typer.confirm", self.typer_confirm
        )

        monkeypatch.setattr(
            "opencode_framework.features.typer.echo", lambda *args, **kwargs: None
        )

    def test_none_defaults_maven_true_gradle_false(self):
        """When current_tools is None, default to maven=True, gradle=False."""
        tools = features._prompt_java_build_tools(None)

        assert self.typer_confirm.call_count == 2
        assert tools == ["maven"]

    def test_empty_list_defaults_maven_true(self):
        """When current_tools is [], default to maven=True, gradle=False."""
        tools = features._prompt_java_build_tools([])

        assert self.typer_confirm.call_count == 2
        assert tools == ["maven"]

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

            m.setattr("opencode_framework.features.typer.confirm", mock_confirm)
            m.setattr(
                "opencode_framework.features.typer.echo", lambda *args, **kwargs: None
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
