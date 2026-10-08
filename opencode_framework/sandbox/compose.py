"""Docker Compose file generation."""

import re
from typing import List, Optional

from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    get_tool_spec,
    managed_volume_keys,
    managed_volume_name,
)
from opencode_framework.config import host_ssh_dir_path
from opencode_framework.generators.base import FileGenerator, GenerationContext
from opencode_framework.generators.templates import (
    BASE_SECURITY_LINES,
    GITCONFIG_MOUNT_LINE,
    M2_SETTINGS_MOUNT_LINE,
    NPMRC_MOUNT_LINE,
    PODMAN_CAPS_GRAPH_ROOT_TARGET,
    PODMAN_CAPS_SECURITY_LINES,
    PODMAN_GRAPH_ROOT_TARGET,
    PODMAN_SECURITY_LINES,
    SSH_MOUNT_LINE,
    TemplateHandler,
)


class ComposeGenerator(FileGenerator):
    """Generates docker-compose.yaml for the tool's config directory."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate docker-compose.yaml from template.

        The template uses environment variable interpolation:
        - PWD: Set at launch time to repo root
        - Other vars: Loaded from the config dir's .env

        Args:
            ctx: Generation context with repo_root, optional_features, etc.
        """
        compose_path = ctx.config_dir / "docker-compose.yaml"
        compose_content = TemplateHandler.render_compose_template(
            repo_root_name=ctx.repo_root.name,
            optional_features=ctx.optional_features,
            port_mappings=ctx.port_mappings,
            java_build_tools=ctx.java_build_tools,
            agent_tool=ctx.agent_tool,
            podman_caps=ctx.podman_caps,
        )
        compose_path.write_text(compose_content)

    @staticmethod
    def detect_ports(compose_text: str) -> List[str]:
        """Extract port mappings from an existing compose file.

        Scans for a service-level ``ports:`` key and collects its list
        children (``- <spec>`` lines).

        Args:
            compose_text: Current docker-compose.yaml content

        Returns:
            List of port specs (e.g. ``["8080:8080", "3000:3000"]``)
        """
        lines = compose_text.split("\n")
        ports: List[str] = []
        in_ports = False
        for line in lines:
            if not in_ports:
                if line == "    ports:":
                    in_ports = True
                continue
            if line.startswith("      - "):
                ports.append(line.strip()[2:])
            elif line.strip() == "":
                continue
            else:
                in_ports = False
        return ports

    @staticmethod
    def rebuild_features(
        compose_text: str,
        repo_name: str,
        optional_features: List[str],
        port_mappings: Optional[List[str]] = None,
        java_build_tools: Optional[List[str]] = None,
        agent_tool: str = DEFAULT_TOOL,
        podman_caps: bool = False,
    ) -> str:
        """Surgically update feature-dependent parts of a compose file.

        Strips the managed feature footprints (security block, python/java
        volume mounts and their top-level volume keys, the entrypoint, the
        managed ports block, the host dotfile mirror mounts, plus the
        legacy DinD privileged line and ``/var/lib/docker`` volume) and
        re-injects only those for the requested feature set.  All other
        lines (environment, custom mounts, user-added security list
        entries, user-added volumes) are preserved.

        When ``port_mappings`` is ``None`` the ports block is left untouched.
        When it is a list (including empty) the ports block is reconciled to
        exactly that set.

        ``podman_caps`` selects the docker feature's mode: caps mode
        (rootless outer daemon) mounts the graph root at
        ``/var/lib/containers`` and injects the caps security block
        (``SYS_ADMIN``/``NET_ADMIN``); standard mode mounts the pinned
        vscode graph root and injects the cap-free podman security block.
        Both modes' managed lines are always stripped, so a mode flip
        reconciles cleanly in either direction.

        Idempotent: applying the same feature set twice yields identical output.

        Args:
            compose_text: Current docker-compose.yaml content
            repo_name: Repository name (used in managed volume names)
            optional_features: Final feature set to apply
            port_mappings: Desired port mappings, or None to leave ports as-is
            java_build_tools: Enabled Java build tools (e.g., ["maven"], ["gradle"]).
                Empty/None mounts no build-tool volumes.
            agent_tool: Agent tool name ("opencode" | "qwen" | "dsh")
            podman_caps: Caps-mode selector for the docker feature

        Returns:
            Updated compose file content
        """
        spec = get_tool_spec(agent_tool)
        venv_mount = (
            f"      - {managed_volume_name('venv', repo_name, spec.name)}:"
            f"${{OCF_LOCAL_REPO_ROOT:-${{PWD}}}}/.venv"
        )
        # Pre-OCF_LOCAL_REPO_ROOT files mounted the venv at /<repo>/.venv;
        # kept here so feature rebuilds strip the legacy line too.
        legacy_venv_mount = (
            f"      - {managed_volume_name('venv', repo_name, spec.name)}:"
            f"/{repo_name}/.venv"
        )
        m2_mount = (
            f"      - {managed_volume_name('m2', repo_name, spec.name)}:"
            f"/home/${{REMOTE_USER}}/.m2"
        )
        gradle_mount = (
            f"      - {managed_volume_name('gradle', repo_name, spec.name)}:"
            f"/home/${{REMOTE_USER}}/.gradle"
        )
        # Pre-wrapper files mounted the graph root under the remote
        # user's home; kept here so feature rebuilds strip the legacy
        # line too. The wrapper runs podman as the vscode service
        # account regardless of REMOTE_USER (see
        # PODMAN_DOCKERFILE_BLOCK), so the target is now pinned.
        legacy_docker_mount = (
            f"      - {managed_volume_name('docker', repo_name, spec.name)}:"
            f"/home/${{REMOTE_USER}}/.local/share/containers"
        )
        docker_mount = (
            f"      - {managed_volume_name('docker', repo_name, spec.name)}:"
            f"{PODMAN_GRAPH_ROOT_TARGET}"
        )
        # Caps-mode graph root (rootless outer daemon): podman runs
        # rootful, default graph root /var/lib/containers (see
        # PODMAN_CAPS_DOCKERFILE_BLOCK).
        caps_docker_mount = (
            f"      - {managed_volume_name('docker', repo_name, spec.name)}:"
            f"{PODMAN_CAPS_GRAPH_ROOT_TARGET}"
        )
        # Legacy Docker-in-Docker mount (pre-podman harnesses): same
        # managed volume name, old dockerd graph root target.
        legacy_dind_mount = (
            f"      - {managed_volume_name('docker', repo_name, spec.name)}:"
            f"/var/lib/docker"
        )
        m2_settings_mount = M2_SETTINGS_MOUNT_LINE
        npmrc_mount = NPMRC_MOUNT_LINE
        gitconfig_mount = GITCONFIG_MOUNT_LINE
        ssh_mount = SSH_MOUNT_LINE
        managed_volume_entries = (
            managed_volume_keys("venv", repo_name, spec.name)
            + managed_volume_keys("m2", repo_name, spec.name)
            + managed_volume_keys("gradle", repo_name, spec.name)
            + managed_volume_keys("docker", repo_name, spec.name)
        )
        # Security-block lines are managed: the base, podman and caps
        # variants are all stripped, then the desired variant is
        # re-injected. ``privileged: true`` is legacy (pre-podman DinD)
        # and only ever stripped. Block keys (security_opt/cap_add/
        # devices) are kept when they carry non-managed children (user
        # additions).
        security_lines = list(
            dict.fromkeys(
                PODMAN_CAPS_SECURITY_LINES + PODMAN_SECURITY_LINES + BASE_SECURITY_LINES
            )
        )
        block_keys = ("    security_opt:", "    cap_add:", "    devices:")
        managed_lines = {
            venv_mount,
            legacy_venv_mount,
            m2_mount,
            m2_settings_mount,
            gradle_mount,
            docker_mount,
            caps_docker_mount,
            legacy_docker_mount,
            legacy_dind_mount,
            npmrc_mount,
            gitconfig_mount,
            ssh_mount,
            f"  {managed_volume_name('venv', repo_name, spec.name)}:",
            f"  {managed_volume_name('m2', repo_name, spec.name)}:",
            f"  {managed_volume_name('gradle', repo_name, spec.name)}:",
            f"  {managed_volume_name('docker', repo_name, spec.name)}:",
            *managed_volume_entries,
            *security_lines,
            "    privileged: true",
        }

        has_docker = "docker" in optional_features
        desired_entrypoint = f'["{spec.binary}"]'

        # Determine which Java build tools are enabled
        tools = java_build_tools or []
        has_maven = "maven" in tools
        has_gradle = "gradle" in tools

        lines = compose_text.split("\n")

        if port_mappings is not None:
            lines = ComposeGenerator._strip_managed_ports(lines)

        # Pass 1: drop managed footprints, rewrite entrypoint value.
        # Block keys (security_opt/cap_add/devices) survive when they
        # carry non-managed list children (user additions); otherwise
        # they are dropped along with their managed children.
        out: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line in block_keys and line in managed_lines:
                j = i + 1
                has_custom_child = False
                while j < len(lines) and lines[j].startswith("      - "):
                    if lines[j] not in managed_lines:
                        has_custom_child = True
                    j += 1
                if has_custom_child:
                    out.append(line)
                    i += 1
                    continue
            if line in managed_lines:
                i += 1
                continue
            match = re.match(r"^(\s*entrypoint:\s*)(.*)$", line)
            if match:
                out.append(f"{match.group(1)}{desired_entrypoint}")
                i += 1
                continue
            out.append(line)
            i += 1
        lines = out

        # Pass 2: drop orphaned empty top-level volumes: header.
        lines = ComposeGenerator._drop_empty_volumes_header_lines(lines)

        # Normalize: collapse trailing blank lines before re-injecting.
        lines = ComposeGenerator._strip_trailing_blank_lines(lines)

        # Pass 3: re-inject footprints for the desired feature set.
        if has_docker:
            security_block = list(
                PODMAN_CAPS_SECURITY_LINES if podman_caps else PODMAN_SECURITY_LINES
            )
        else:
            security_block = list(BASE_SECURITY_LINES)
        lines = ComposeGenerator._insert_after_block(
            lines, "    working_dir", security_block
        )

        # Injection order must match render_compose_template exactly so a
        # fresh render survives the reconciler unchanged.
        mounts: List[str] = []
        mounts.append(npmrc_mount)
        mounts.append(gitconfig_mount)
        if "python" in optional_features:
            mounts.append(venv_mount)
        if "java" in optional_features:
            if has_maven:
                mounts.append(m2_mount)
                mounts.append(m2_settings_mount)
            if has_gradle:
                mounts.append(gradle_mount)
        if has_docker:
            mounts.append(caps_docker_mount if podman_caps else docker_mount)
        # Directory target: no /dev/null fallback, so the line is only
        # injected when the feature is on and the host ~/.ssh exists
        # (mirrors the fresh-render gate in render_compose_template).
        if host_ssh_dir_path("ssh" in optional_features):
            mounts.append(ssh_mount)
        if mounts:
            lines = ComposeGenerator._insert_before_line(
                lines, "    entrypoint", mounts
            )

        vol_keys: List[str] = []
        if "python" in optional_features:
            vol_keys.extend(managed_volume_keys("venv", repo_name, spec.name))
        if has_docker:
            vol_keys.extend(managed_volume_keys("docker", repo_name, spec.name))
        if "java" in optional_features:
            if has_maven:
                vol_keys.extend(managed_volume_keys("m2", repo_name, spec.name))
            if has_gradle:
                vol_keys.extend(managed_volume_keys("gradle", repo_name, spec.name))
        if vol_keys:
            lines = ComposeGenerator._ensure_volumes_block_lines(lines, vol_keys)

        if port_mappings:
            port_block = ["    ports:"] + [f"      - {p}" for p in port_mappings]
            lines = ComposeGenerator._insert_after_block(
                lines, "    working_dir", port_block
            )

        return "\n".join(lines) + "\n"

    @staticmethod
    def _strip_managed_ports(lines: List[str]) -> List[str]:
        """Remove a managed '    ports:' key and its list children."""
        out: List[str] = []
        in_ports = False
        for line in lines:
            if not in_ports:
                if line == "    ports:":
                    in_ports = True
                else:
                    out.append(line)
                continue
            if line.startswith("      - "):
                continue
            if line.strip() == "":
                continue
            in_ports = False
            out.append(line)
        return out

    @staticmethod
    def _strip_trailing_blank_lines(lines: List[str]) -> List[str]:
        result = list(lines)
        while result and result[-1].strip() == "":
            result.pop()
        return result

    @staticmethod
    def _drop_empty_volumes_header_lines(lines: List[str]) -> List[str]:
        out: List[str] = []
        i = 0
        while i < len(lines):
            if ComposeGenerator._is_top_level_key(lines[i], "volumes:"):
                j = i + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                has_child = j < len(lines) and (
                    lines[j].startswith(" ") or lines[j].startswith("\t")
                )
                if not has_child:
                    i += 1
                    continue
            out.append(lines[i])
            i += 1
        return out

    @staticmethod
    def _insert_after_line(lines: List[str], prefix: str, content: str) -> List[str]:
        out: List[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.startswith(prefix):
                out.append(content)
                inserted = True
        return out

    @staticmethod
    def _insert_after_block(
        lines: List[str], prefix: str, contents: List[str]
    ) -> List[str]:
        out: List[str] = []
        inserted = False
        for line in lines:
            out.append(line)
            if not inserted and line.startswith(prefix):
                out.extend(contents)
                inserted = True
        return out

    @staticmethod
    def _insert_before_line(
        lines: List[str], prefix: str, contents: List[str]
    ) -> List[str]:
        out: List[str] = []
        inserted = False
        for line in lines:
            if not inserted and line.startswith(prefix):
                out.extend(contents)
                inserted = True
            out.append(line)
        return out

    @staticmethod
    def _ensure_volumes_block_lines(lines: List[str], vol_keys: List[str]) -> List[str]:
        idx: int = -1
        for i, line in enumerate(lines):
            if ComposeGenerator._is_top_level_key(line, "volumes:"):
                idx = i
                break
        if idx >= 0:
            return lines[: idx + 1] + vol_keys + lines[idx + 1 :]
        return lines + ["", "volumes:"] + vol_keys

    @staticmethod
    def _is_top_level_key(line: str, key: str) -> bool:
        """True if line is a YAML key at column 0 (no indentation)."""
        return not line[:1].isspace() and line.strip() == key
