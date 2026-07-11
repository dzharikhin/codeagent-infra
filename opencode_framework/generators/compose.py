"""Docker Compose file generation."""

import re
from typing import List, Optional

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class ComposeGenerator(FileGenerator):
    """Generates .opencode/docker-compose.yaml for runtime."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate docker-compose.yaml from template.

        The template uses environment variable interpolation:
        - PWD: Set at launch time to repo root
        - Other vars: Loaded from .opencode/.env

        Args:
            ctx: Generation context with repo_root, optional_features, etc.
        """
        compose_path = ctx.opencode_dir / "docker-compose.yaml"
        compose_content = TemplateHandler.render_compose_template(
            repo_root_name=ctx.repo_root.name,
            optional_features=ctx.optional_features,
            port_mappings=ctx.port_mappings,
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
    ) -> str:
        """Surgically update feature-dependent parts of a compose file.

        Strips the managed feature footprints (privileged line, python/java
        volume mounts and their top-level volume keys, the docker-init
        entrypoint, the managed ports block) and re-injects only those for
        the requested feature set.  All other lines (environment, custom
        mounts, security_opt, user-added volumes) are preserved.

        When ``port_mappings`` is ``None`` the ports block is left untouched.
        When it is a list (including empty) the ports block is reconciled to
        exactly that set.

        Idempotent: applying the same feature set twice yields identical output.

        Args:
            compose_text: Current docker-compose.yaml content
            repo_name: Repository name (used in managed volume names)
            optional_features: Final feature set to apply
            port_mappings: Desired port mappings, or None to leave ports as-is

        Returns:
            Updated compose file content
        """
        venv_mount = f"      - venv-{repo_name}:/{repo_name}/.venv"
        m2_mount = f"      - m2-{repo_name}:/home/${{REMOTE_USER}}/.m2"
        managed_lines = {
            venv_mount,
            m2_mount,
            f"  venv-{repo_name}:",
            f"  m2-{repo_name}:",
            "    privileged: true",
        }

        has_docker = "docker" in optional_features
        desired_entrypoint = (
            '["/usr/local/share/docker-init.sh", "opencode"]'
            if has_docker
            else '["opencode"]'
        )

        lines = compose_text.split("\n")

        if port_mappings is not None:
            lines = ComposeGenerator._strip_managed_ports(lines)

        # Pass 1: drop managed footprints, rewrite entrypoint value.
        out: List[str] = []
        for line in lines:
            if line in managed_lines:
                continue
            match = re.match(r'^(\s*entrypoint:\s*)(.*)$', line)
            if match:
                out.append(f"{match.group(1)}{desired_entrypoint}")
                continue
            out.append(line)
        lines = out

        # Pass 2: drop orphaned empty top-level volumes: header.
        lines = ComposeGenerator._drop_empty_volumes_header_lines(lines)

        # Normalize: collapse trailing blank lines before re-injecting.
        lines = ComposeGenerator._strip_trailing_blank_lines(lines)

        # Pass 3: re-inject footprints for the desired feature set.
        if has_docker:
            lines = ComposeGenerator._insert_after_line(
                lines, "    working_dir", "    privileged: true"
            )

        mounts: List[str] = []
        if "python" in optional_features:
            mounts.append(venv_mount)
        if "java" in optional_features:
            mounts.append(m2_mount)
        if mounts:
            lines = ComposeGenerator._insert_before_line(
                lines, "    entrypoint", mounts
            )

        vol_keys: List[str] = []
        if "python" in optional_features:
            vol_keys.append(f"  venv-{repo_name}:")
        if "java" in optional_features:
            vol_keys.append(f"  m2-{repo_name}:")
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
                has_child = (
                    j < len(lines)
                    and (lines[j].startswith(" ") or lines[j].startswith("\t"))
                )
                if not has_child:
                    i += 1
                    continue
            out.append(lines[i])
            i += 1
        return out

    @staticmethod
    def _insert_after_line(
        lines: List[str], prefix: str, content: str
    ) -> List[str]:
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
    def _ensure_volumes_block_lines(
        lines: List[str], vol_keys: List[str]
    ) -> List[str]:
        idx: int = -1
        for i, line in enumerate(lines):
            if ComposeGenerator._is_top_level_key(line, "volumes:"):
                idx = i
                break
        if idx >= 0:
            return lines[: idx + 1] + vol_keys + lines[idx + 1:]
        return lines + ["", "volumes:"] + vol_keys

    @staticmethod
    def _is_top_level_key(line: str, key: str) -> bool:
        """True if line is a YAML key at column 0 (no indentation)."""
        return not line[:1].isspace() and line.strip() == key
