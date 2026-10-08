"""Tests for .opencode/ directory generation."""

import json
import subprocess
import tomllib
from pathlib import Path

from opencode_framework.agent.registry import DSH_TOOL_SPEC, get_tool_spec
from opencode_framework.config import GlobalSettings
from opencode_framework.generators.base import GenerationContext
from opencode_framework.generators.config_files import ConfigFilesGenerator
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.generators.orchestrator import GenerationOrchestrator
from opencode_framework.generators.templates import (
    GITCONFIG_MOUNT_LINE,
    M2_SETTINGS_MOUNT_LINE,
    NPMRC_MOUNT_LINE,
    SSH_MOUNT_LINE,
    TemplateHandler,
)
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.devcontainer import DevcontainerGenerator
from opencode_framework.wizard import WizardResult


def _make_global_settings(**kwargs):
    """Create GlobalSettings with defaults."""
    defaults = {"framework_repo_path": None}
    defaults.update(kwargs)
    return GlobalSettings(**defaults)


def _make_generation_context(tmp_path: Path, **kwargs):
    """Create GenerationContext with defaults."""
    defaults = {
        "repo_root": tmp_path,
        "config_dir": tmp_path / ".opencode",
        "branch_name": "codeagent-test",
        "optional_features": [],
        "global_settings": _make_global_settings(),
    }
    defaults.update(kwargs)
    return GenerationContext(**defaults)


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
            optional_features=[],
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

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
            optional_features=[],
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        dc_content = json.loads((opencode_dir / "devcontainer.json").read_text())
        assert "name" in dc_content
        assert "features" in dc_content


class TestAddOptionalFeatures:
    """Tests for optional feature addition."""

    def test_docker_feature(self):
        """Docker feature should merge podman packages into the apt-packages feature."""
        features = {
            "ghcr.io/devcontainers-extra/features/apt-packages:1": {
                "packages": "ripgrep"
            }
        }
        DevcontainerGenerator._add_optional_features(features, ["docker"])
        apt = features["ghcr.io/devcontainers-extra/features/apt-packages:1"]
        pkgs = apt["packages"].split(",")
        assert "ripgrep" in pkgs
        assert "podman" in pkgs
        assert "podman-docker" in pkgs

    def test_python_feature(self):
        """Python feature should add Python feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["python"])
        assert "ghcr.io/devcontainers/features/python:1" in features

    def test_nodejs_feature(self):
        """Node.js feature should add Node feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["nodejs"])
        assert "ghcr.io/devcontainers/features/node:1" in features

    def test_java_feature(self):
        """Java feature should add Java feature."""
        features = {}
        DevcontainerGenerator._add_optional_features(features, ["java"])
        assert "ghcr.io/devcontainers/features/java:1" in features


class TestDevcontainerGenerator:
    """Tests for devcontainer generator."""

    def test_scratch_has_features(self, tmp_path: Path):
        """Scratch devcontainer should have features."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DevcontainerGenerator()
        gen.generate(ctx)

        dc_content = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )
        assert "features" in dc_content
        assert "ghcr.io/devcontainers/features/git:1" in dc_content["features"]

    def test_remote_user_uses_env_var(self, tmp_path: Path):
        """Devcontainer should use REMOTE_USER env var."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DevcontainerGenerator()
        gen.generate(ctx)

        dc_content = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )
        assert "REMOTE_USER" in dc_content.get("remoteUser", "")

    def test_ripgrep_installed_by_default(self, tmp_path: Path):
        """apt-packages feature should install ripgrep by default."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DevcontainerGenerator()
        gen.generate(ctx)

        dc_content = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )
        features = dc_content["features"]
        apt_packages = features["ghcr.io/devcontainers-extra/features/apt-packages:1"]
        assert "ripgrep" in apt_packages["packages"]
        common_utils = features["ghcr.io/devcontainers/features/common-utils:2"]
        assert "installPackages" not in common_utils

    def test_podman_block_bakes_docker_wrapper(self):
        """Podman block should bake the /usr/local/bin/docker wrapper
        that drops root agents to the (pre-existing) vscode account,
        unsetting the agent's XDG vars so podman's rootless graph root
        stays under /home/vscode."""
        block = DevcontainerGenerator.PODMAN_DOCKERFILE_BLOCK
        assert "mkdir -p /etc/containers && touch /etc/containers/nodocker" in block
        assert "useradd" not in block
        assert "runuser -u vscode -- /usr/bin/env" in block
        assert "-u XDG_DATA_HOME -u XDG_CONFIG_HOME" in block
        assert "-u XDG_STATE_HOME -u XDG_CACHE_HOME" in block
        assert 'XDG_CACHE_HOME /usr/bin/podman "$@"' in block
        assert "exec /usr/bin/podman" in block
        assert "> /usr/local/bin/docker" in block
        assert "command -v docker | grep -q '^/usr/local/bin/docker$'" in block
        assert "ENV BUILDAH_ISOLATION=chroot" in block
        # Minimal containers.conf bake: cgroup creation must be disabled
        # (the sandbox's /sys/fs/cgroup is read-only), engine fallbacks
        # pinned, storage driver stays auto-detected (no vfs pin).
        assert "'[containers]'" in block
        assert "'cgroups = \"disabled\"'" in block
        assert "'[engine]'" in block
        assert "'cgroup_manager = \"cgroupfs\"'" in block
        assert "'events_logger = \"file\"'" in block
        assert (
            "grep -q 'cgroups = \"disabled\"' /etc/containers/containers.conf" in block
        )
        assert 'driver = "vfs"' not in block

    def test_podman_block_bakes_graph_root_ownership(self):
        """Graph-root directory must be baked vscode-owned so a fresh
        named volume's copy-up inherits that ownership."""
        block = DevcontainerGenerator.PODMAN_DOCKERFILE_BLOCK
        assert (
            "mkdir -p /home/vscode/.local/share/containers && \\\n"
            "    chown vscode:vscode /home/vscode/.local/share/containers"
        ) in block

    def test_podman_block_rendered_when_docker_enabled(self, tmp_path: Path):
        """Dockerfile written by initializeCommand should contain the
        wrapper only when the docker feature is enabled."""
        for feats, present in ((["docker"], True), ([], False)):
            (tmp_path / ".opencode").mkdir(exist_ok=True)
            ctx = _make_generation_context(tmp_path, optional_features=feats)
            gen = DevcontainerGenerator()
            gen.generate(ctx)
            initialize = json.loads(
                (tmp_path / ".opencode" / "devcontainer.json").read_text()
            )["initializeCommand"]
            assert ("runuser -u vscode" in initialize) is present
            assert ("/usr/local/bin/docker" in initialize) is present

    def test_initializer_heredoc_roundtrip(self, tmp_path: Path):
        """initializeCommand must write the Dockerfile byte-for-byte via
        a quoted heredoc (no echo -e backslash mangling)."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path, optional_features=["docker"])
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        initialize = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )["initializeCommand"]
        assert "echo -e" not in initialize
        assert "<<'OCF_DOCKERFILE_EOF'" in initialize
        # Simulate the shell: extract the heredoc body and compare with
        # the expected content (template + rendered block).
        body = initialize.split("<<'OCF_DOCKERFILE_EOF'\n", 1)[1]
        body = body.rsplit("OCF_DOCKERFILE_EOF", 1)[0]
        expected = TemplateHandler.load_dockerfile_template().replace(
            "{{PODMAN_SUPPORT}}\n",
            DevcontainerGenerator.PODMAN_DOCKERFILE_BLOCK + "\n",
        )
        install_block = DevcontainerGenerator._build_install_block(
            get_tool_spec("opencode")
        )
        if install_block:
            expected = expected.replace("{{AGENT_INSTALL}}", install_block)
        else:
            expected = expected.replace("\n{{AGENT_INSTALL}}", "")
        assert body == expected
        # The printf escape sequence must survive verbatim.
        assert "printf '%s\\n'" in body

    def test_podman_caps_block_bakes_rootful_engine(self):
        """Caps block bakes rootful podman for the root agent: conf bake
        with its assertion (storage driver auto-detected — the vfs pin
        was a silent no-op, [storage] is not a containers.conf table), a
        root-only wrapper branch that remounts /proc/sys tolerantly, no
        runuser/vscode delegation and no graph-root ownership bake."""
        block = DevcontainerGenerator.PODMAN_CAPS_DOCKERFILE_BLOCK
        # containers.conf bake (rootful fallbacks) with assertions.
        assert "mkdir -p /etc/containers && touch /etc/containers/nodocker" in block
        assert "'[containers]'" in block
        assert 'cgroup_manager = "cgroupfs"' in block
        assert 'events_logger = "file"' in block
        assert 'cgroups = "disabled"' in block
        assert (
            "grep -q 'cgroups = \"disabled\"' /etc/containers/containers.conf" in block
        )
        # Storage driver stays auto-detected: no vfs pin anywhere.
        assert "'[storage]'" not in block
        assert 'driver = "vfs"' not in block
        # Wrapper: root branch remounts /proc/sys (tolerant) and execs
        # podman directly; non-root agents get plain rootless podman.
        assert '[ "$(id -u)" = "0" ] && {' in block
        assert "mount -o remount,rw /proc/sys 2>/dev/null || true" in block
        assert 'exec /usr/bin/podman "$@"' in block
        # No vscode delegation anywhere.
        assert "runuser" not in block
        assert "vscode" not in block
        # No graph-root ownership bake (rootful graph root is /var/lib/
        # containers and root writes it freely).
        assert "chown" not in block
        # PATH assertion lives in the wrapper RUN (after chmod +x).
        assert "chmod +x /usr/local/bin/docker" in block
        assert "command -v docker | grep -q '^/usr/local/bin/docker$'" in block
        assert "ENV BUILDAH_ISOLATION=chroot" in block

    def test_podman_caps_initializer_heredoc_roundtrip(self, tmp_path: Path):
        """With podman_caps the initializeCommand heredoc must carry the
        caps Dockerfile block byte-for-byte."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(
            tmp_path, optional_features=["docker"], podman_caps=True
        )
        gen = DevcontainerGenerator()
        gen.generate(ctx)
        initialize = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )["initializeCommand"]
        body = initialize.split("<<'OCF_DOCKERFILE_EOF'\n", 1)[1]
        body = body.rsplit("OCF_DOCKERFILE_EOF", 1)[0]
        expected = TemplateHandler.load_dockerfile_template().replace(
            "{{PODMAN_SUPPORT}}\n",
            DevcontainerGenerator.PODMAN_CAPS_DOCKERFILE_BLOCK + "\n",
        )
        install_block = DevcontainerGenerator._build_install_block(
            get_tool_spec("opencode")
        )
        if install_block:
            expected = expected.replace("{{AGENT_INSTALL}}", install_block)
        else:
            expected = expected.replace("\n{{AGENT_INSTALL}}", "")
        assert body == expected
        assert "mount -o remount,rw /proc/sys" in body

    def test_podman_caps_wrapper_script_valid_shell(self, tmp_path: Path):
        """The baked wrapper script must be valid POSIX shell and exec
        podman on both branches. The script is reconstructed here exactly
        as the block's printf lines emit it."""
        block = DevcontainerGenerator.PODMAN_CAPS_DOCKERFILE_BLOCK
        script = (
            "#!/bin/sh\n"
            '[ "$(id -u)" = "0" ] && {'
            " mount -o remount,rw /proc/sys 2>/dev/null || true;"
            ' exec /usr/bin/podman "$@"; }\n'
            'exec /usr/bin/podman "$@"\n'
        )
        # Every emitted line must come verbatim from the block.
        for line in script.split("\n"):
            if line:
                assert line in block
        proc = subprocess.run(
            ["sh", "-n"],
            input=script,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr

    @staticmethod
    def _exec_conf_run(block: str, tmp_path: Path) -> dict:
        """Execute a block's containers.conf RUN via real sh and parse
        the produced file with tomllib.

        The first ``RUN printf`` in both podman blocks is the conf bake.
        Its redirect/grep target is rewritten to a temp path (the RUN
        only writes and greps the file — no other absolute paths are
        involved). Structural placement is asserted by the callers: a
        key in the wrong TOML table lands somewhere else and the caller's
        lookup misses.
        """
        lines = block.split("\n")
        start = next(i for i, ln in enumerate(lines) if ln.startswith("RUN printf"))
        run_lines = []
        for ln in lines[start:]:
            run_lines.append(ln)
            if not ln.endswith("\\"):
                break
        run_text = "\n".join(run_lines)[len("RUN ") :]
        conf_path = tmp_path / "containers.conf"
        run_text = run_text.replace("/etc/containers/containers.conf", str(conf_path))
        proc = subprocess.run(["sh", "-c", run_text], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        with open(conf_path, "rb") as fh:
            return tomllib.load(fh)

    def test_standard_conf_section_placement(self, tmp_path: Path):
        """The standard block's conf must disable cgroups under the
        [containers] table (a [containers]-table key — misplaced under
        [engine], podman never applies it and runs die on the sandbox's
        read-only /sys/fs/cgroup), pin the engine fallbacks, and leave
        the storage driver auto-detected."""
        conf = self._exec_conf_run(
            DevcontainerGenerator.PODMAN_DOCKERFILE_BLOCK, tmp_path
        )
        assert conf["containers"]["cgroups"] == "disabled"
        assert conf["engine"]["cgroup_manager"] == "cgroupfs"
        assert conf["engine"]["events_logger"] == "file"
        assert "storage" not in conf

    def test_caps_conf_section_placement(self, tmp_path: Path):
        """The caps block's conf matches the standard bake: cgroups
        disabled under [containers], engine fallbacks pinned, storage
        driver auto-detected (rootful podman mounts real overlay — the
        vfs pin sat silently ignored because [storage] is not a
        containers.conf table)."""
        conf = self._exec_conf_run(
            DevcontainerGenerator.PODMAN_CAPS_DOCKERFILE_BLOCK, tmp_path
        )
        assert conf["containers"]["cgroups"] == "disabled"
        assert conf["engine"]["cgroup_manager"] == "cgroupfs"
        assert conf["engine"]["events_logger"] == "file"
        assert "storage" not in conf


class TestOpenCodeFeature:
    """Tests for OpenCode feature inclusion."""

    def test_opencode_feature_in_scratch(self, tmp_path: Path):
        """Scratch devcontainer should include OpenCode feature."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DevcontainerGenerator()
        gen.generate(ctx)

        dc_content = json.loads(
            (tmp_path / ".opencode" / "devcontainer.json").read_text()
        )
        assert (
            "ghcr.io/jsburckhardt/devcontainer-features/opencode:1.1.1"
            in dc_content["features"]
        )

        feature = dc_content["features"][
            "ghcr.io/jsburckhardt/devcontainer-features/opencode:1.1.1"
        ]
        assert "version" in feature
        assert "OCF_AGENT_VERSION" in feature["version"]


class TestEnvFileGeneration:
    """Tests for .env file generation."""

    def test_env_contains_remote_user(self, tmp_path: Path):
        """Generated .env should contain REMOTE_USER (root by default:
        container root maps to the host user on rootless daemons, so
        bind-mount writes succeed regardless of daemon mode)."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = ConfigFilesGenerator()
        gen.generate(ctx)

        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "REMOTE_USER=root" in env_content

    def test_env_contains_xdg_vars(self, tmp_path: Path):
        """Generated .env should contain XDG variables."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = ConfigFilesGenerator()
        gen.generate(ctx)

        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "XDG_CONFIG_HOME" in env_content
        assert "XDG_DATA_HOME" in env_content
        assert "XDG_STATE_HOME" in env_content
        assert "XDG_CACHE_HOME" in env_content

    def test_env_contains_model_vars(self, tmp_path: Path):
        """Generated .env should contain model configuration vars."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = ConfigFilesGenerator()
        gen.generate(ctx)

        env_content = (tmp_path / ".opencode" / ".env").read_text()
        assert "OCF_MAIN_MODEL" in env_content
        assert "OCF_BUILD_MODEL" in env_content
        assert "OCF_SMALL_MODEL" in env_content

    def test_env_does_not_bake_repo_root_path(self, tmp_path: Path):
        """.env must not bake the repo location; launch derives it per-run."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        (repo_root / ".opencode").mkdir()
        ctx = _make_generation_context(repo_root)

        gen = ConfigFilesGenerator()
        gen.generate(ctx)

        env_content = (repo_root / ".opencode" / ".env").read_text()
        assert "OCF_LOCAL_REPO_ROOT" not in env_content


class TestLaunchCommands:
    """Tests for host-side launch command generation."""

    def test_launch_command_is_cli(self):
        """Launch command should use ocframework CLI."""
        commands = DocumentationGenerator.get_launch_commands("opencode")
        assert commands["launch"] == "ocframework launch --tool opencode"

    def test_debug_command_is_cli(self):
        """Debug command should use ocframework launch with debug subcommand."""
        commands = DocumentationGenerator.get_launch_commands("opencode")
        assert commands["debug"] == "ocframework launch --tool opencode -- debug config"

    def test_shell_command_is_docker_exec(self):
        """Shell command should use docker exec directly."""
        commands = DocumentationGenerator.get_launch_commands("opencode")
        assert commands["shell"] == "docker exec -it <container_name> /bin/bash"

    def test_acp_command_for_supported_tools(self):
        """ACP command uses --acp with a postfix for tools with a stdio mode."""
        assert (
            DocumentationGenerator.get_launch_commands("opencode")["acp"]
            == "ocframework launch --tool opencode --acp <postfix>"
        )
        assert (
            DocumentationGenerator.get_launch_commands("qwen")["acp"]
            == "ocframework launch --tool qwen --acp <postfix>"
        )

    def test_acp_command_falls_back_to_server_for_dsh(self):
        """dsh has no ACP mode; docs point at the Web UI instead."""
        assert (
            DocumentationGenerator.get_launch_commands("dsh")["acp"]
            == "ocframework launch --tool dsh --server"
        )


class TestReadmeLaunchCommand:
    """Tests for README launch command content."""

    def test_readme_shows_cli_launch(self, tmp_path: Path):
        """README should show CLI launch command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DocumentationGenerator()
        gen.generate(ctx)

        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "ocframework launch" in readme_content

    def test_readme_has_debug_command(self, tmp_path: Path):
        """README should show debug command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DocumentationGenerator()
        gen.generate(ctx)

        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "launch --tool opencode -- debug config" in readme_content

    def test_readme_has_shell_command(self, tmp_path: Path):
        """README should show shell command."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DocumentationGenerator()
        gen.generate(ctx)

        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "### Shell" in readme_content


class TestReadmeToolSections:
    """Tests for per-tool README sections driven by agent_tool."""

    @staticmethod
    def _render(agent_tool: str) -> str:
        return TemplateHandler.render_readme_template(
            launch_command="ocframework launch",
            reconfigure_command="ocframework reconfigure",
            debug_command="ocframework launch -- debug config",
            shell_command="docker exec -it <container_name> /bin/bash",
            branch_name="codeagent-test",
            agent_tool=agent_tool,
        )

    def test_opencode_sections(self):
        """opencode README shows opencode models/serve/auth wording."""
        readme = self._render("opencode")
        assert "opencode models" in readme
        assert "OPENCODE_SERVER_PASSWORD" in readme
        assert "container port 4096" in readme
        assert "ghcr.io/jsburckhardt/devcontainer-features/opencode" in readme
        assert "- OpenCode docs: https://opencode.ai" in readme
        # {{LAUNCH_COMMAND}} inside the tool serve section is resolved
        assert "ocframework launch --server" in readme

    def test_qwen_sections(self):
        """qwen README shows qwen serve/token/settings wording."""
        readme = self._render("qwen")
        assert "QWEN_SERVER_TOKEN" in readme
        assert "container port 4170" in readme
        assert "QWEN_CODE_SYSTEM_DEFAULTS_PATH" in readme
        assert "DASHSCOPE_API_KEY" in readme
        assert "@qwen-code/qwen-code" in readme
        assert "- Qwen Code docs: https://github.com/QwenLM/qwen-code" in readme
        assert "ocframework launch --server" in readme

    def test_qwen_sections_exclude_opencode_wording(self):
        """qwen README must not leak opencode-specific content."""
        readme = self._render("qwen")
        assert "opencode models" not in readme
        assert "OPENCODE_SERVER_PASSWORD" not in readme
        assert "https://opencode.ai" not in readme
        assert "devcontainer-features/opencode" not in readme

    def test_dsh_sections(self):
        """dsh README shows dsh serve/token/settings wording."""
        readme = self._render("dsh")
        assert "container port 3080" in readme
        assert "DEEPSEEK_API_KEY" in readme
        assert "@deepseek-ai/dsh" in readme
        assert "?token=" in readme
        assert "no TUI" in readme
        assert "/opt/ocframework/config/dsh/web-bind-all.patch.yml" in readme
        assert "ocframework launch --server" in readme

    def test_dsh_sections_order_patch_before_web_flags(self):
        """serve command must place --patch before the web app flags."""
        readme = self._render("dsh")
        patch_idx = readme.index("--patch")
        no_open_idx = readme.index("--no-open")
        assert patch_idx < no_open_idx

    def test_acp_sections(self):
        """ACP section shows editor integration wording per tool."""
        opencode_readme = self._render("opencode")
        assert "## Connect an Editor (ACP)" in opencode_readme
        assert (
            '"args": ["launch", "--tool", "opencode", "--acp", "zed"]'
            in opencode_readme
        )
        assert "--acp <postfix>" in opencode_readme

        qwen_readme = self._render("qwen")
        assert "## Connect an Editor (ACP)" in qwen_readme
        assert '"args": ["launch", "--tool", "qwen", "--acp", "zed"]' in qwen_readme
        assert "--acp <postfix>" in qwen_readme
        # qwen README must not leak opencode's ACP args
        assert '"launch", "--tool", "opencode"' not in qwen_readme

        dsh_readme = self._render("dsh")
        assert "## Editor Integration (ACP)" in dsh_readme
        assert "no ACP/stdio mode" in dsh_readme
        assert "ocframework launch --server" in dsh_readme

    def test_dsh_sections_exclude_other_tool_wording(self):
        """dsh README must not leak opencode/qwen-specific content."""
        readme = self._render("dsh")
        assert "OPENCODE_SERVER_PASSWORD" not in readme
        assert "QWEN_SERVER_TOKEN" not in readme
        assert "opencode models" not in readme
        assert "devcontainer-features/opencode" not in readme

    def test_no_unresolved_placeholders(self):
        """Rendered README must not contain any template placeholders."""
        for tool in ("opencode", "qwen", "dsh"):
            readme = self._render(tool)
            assert "{{" not in readme

    def test_unknown_tool_rejected(self):
        """An unsupported tool name raises ValidationError."""
        import pytest

        from opencode_framework.exceptions import ValidationError

        with pytest.raises(ValidationError):
            self._render("nope")

    def test_documentation_generator_uses_ctx_tool(self, tmp_path: Path):
        """DocumentationGenerator renders sections for ctx.agent_tool."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path, agent_tool="qwen")

        gen = DocumentationGenerator()
        gen.generate(ctx)

        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "QWEN_SERVER_TOKEN" in readme_content
        assert "https://opencode.ai" not in readme_content


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
            optional_features=[],
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

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
            optional_features=[],
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        runtime_data = opencode_dir / "runtime_data"

        assert not (runtime_data / "logs").exists()
        assert not (runtime_data / "tools").exists()
        assert not (runtime_data / "temp").exists()

    def test_gitignore_ignores_runtime_data(self, tmp_path: Path):
        """gitignore should ignore runtime_data directory."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        wizard_result = WizardResult(
            branch_name="codeagent-test",
            optional_features=[],
        )

        orchestrator = GenerationOrchestrator()
        orchestrator.generate(repo_root, wizard_result)

        gitignore_content = (opencode_dir / ".gitignore").read_text()

        assert "runtime_data/" in gitignore_content


class TestReadmeFrameworkUrl:
    """Tests for README framework URL."""

    def test_readme_has_framework_url(self, tmp_path: Path):
        """README should have framework docs URL."""
        (tmp_path / ".opencode").mkdir()
        ctx = _make_generation_context(tmp_path)

        gen = DocumentationGenerator()
        gen.generate(ctx)

        readme_content = (tmp_path / ".opencode" / "README.md").read_text()
        assert "https://github.com/dzharikhin/codeagent-infra" in readme_content


class TestComposeGenerator:
    """Tests for docker-compose generation."""

    def test_python_feature_adds_venv_volume(self, tmp_path: Path):
        """Python feature should add venv named volume to compose."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["python"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "venv-myproject-opencode" in compose_content
        assert "volumes:" in compose_content
        assert "${OCF_LOCAL_REPO_ROOT:-${PWD}}/.venv" in compose_content

    def test_project_mounted_at_host_path(self, tmp_path: Path):
        """Compose mounts the project at its host path and sets working_dir."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(repo_root)

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "working_dir: ${OCF_LOCAL_REPO_ROOT:-${PWD}}" in compose_content
        assert (
            "- ${OCF_LOCAL_REPO_ROOT:-${PWD}}:${OCF_LOCAL_REPO_ROOT:-${PWD}}"
            in compose_content
        )
        assert "- OCF_LOCAL_REPO_ROOT=${OCF_LOCAL_REPO_ROOT:-${PWD}}" in compose_content
        assert "/myproject" not in compose_content

    def test_no_python_feature_no_venv_volume(self, tmp_path: Path):
        """Without Python feature, no venv volume should be added."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["nodejs"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "venv-" not in compose_content

    def test_compose_has_required_volumes(self, tmp_path: Path):
        """Generated compose should have required volume mounts."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(repo_root)

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "runtime_data" in compose_content
        assert "framework-config" in compose_content
        assert "framework-nuts-and-bolts" in compose_content

    def test_docker_feature_adds_security_and_volume(self, tmp_path: Path):
        """Podman feature adds seccomp=unconfined, /dev/fuse and storage volume."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["docker"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "privileged" not in compose_content
        assert "seccomp=unconfined" in compose_content
        assert "/dev/fuse" in compose_content
        assert "docker-myproject-opencode" in compose_content
        assert ".local/share/containers" in compose_content
        assert '["opencode"]' in compose_content

    def test_docker_feature_caps_mode_adds_caps_block(self, tmp_path: Path):
        """Caps-mode compose renders the SYS_ADMIN/NET_ADMIN caps block
        and mounts the graph root at /var/lib/containers."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["docker"],
            podman_caps=True,
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "cap_add:" in compose_content
        assert "      - SYS_ADMIN" in compose_content
        assert "      - NET_ADMIN" in compose_content
        assert "docker-myproject-opencode:/var/lib/containers" in compose_content
        assert ".local/share/containers" not in compose_content

    def test_docker_feature_standard_mode_no_caps(self, tmp_path: Path):
        """Standard-mode compose stays cap-free and keeps the pinned
        vscode graph root."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["docker"],
            podman_caps=False,
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "SYS_ADMIN" not in compose_content
        assert "NET_ADMIN" not in compose_content
        assert (
            "docker-myproject-opencode:/home/vscode/.local/share/containers"
            in compose_content
        )
        assert "/var/lib/containers" not in compose_content

    def test_no_docker_feature_no_unconfined(self, tmp_path: Path):
        """Without docker feature, no seccomp=unconfined or device passthrough."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["python"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "privileged" not in compose_content
        assert "seccomp=unconfined" not in compose_content
        assert '["opencode"]' in compose_content

    def test_java_feature_adds_m2_volume(self, tmp_path: Path):
        """Java feature with maven should add m2 named volume to compose."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["java"],
            java_build_tools=["maven"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "m2-myproject-opencode" in compose_content
        assert "volumes:" in compose_content
        assert "/home/${REMOTE_USER}/.m2" in compose_content

    def test_java_without_build_tools_no_m2_volume(self, tmp_path: Path):
        """Java feature with empty build tools must not add tool volumes."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["java"],
            java_build_tools=[],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "m2-" not in compose_content
        assert "gradle-" not in compose_content

    def test_no_java_feature_no_m2_volume(self, tmp_path: Path):
        """Without Java feature, no m2 volume should be added."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["python"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "m2-" not in compose_content

    def test_python_and_java_features_both_add_volumes(self, tmp_path: Path):
        """Python and Java features should both add volumes without clobbering."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["python", "java"],
            java_build_tools=["maven"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "venv-myproject-opencode" in compose_content
        assert "m2-myproject-opencode" in compose_content
        assert "${OCF_LOCAL_REPO_ROOT:-${PWD}}/.venv" in compose_content
        assert "/home/${REMOTE_USER}/.m2" in compose_content
        assert (
            compose_content.count("volumes:") == 2
        )  # One in services, one top-level for named volumes

    def test_port_mappings_adds_ports_block(self, tmp_path: Path):
        """Port mappings should produce a ports: block in compose."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            port_mappings=["8080:8080", "3000:3000"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "    ports:" in compose_content
        assert "      - 8080:8080" in compose_content
        assert "      - 3000:3000" in compose_content

    def test_no_port_mappings_no_ports_block(self, tmp_path: Path):
        """Without port mappings, no ports: block should appear."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(repo_root)

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "ports:" not in compose_content

    def test_ports_and_docker_feature_coexist(self, tmp_path: Path):
        """Ports and docker feature should both render without conflict."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()

        ctx = _make_generation_context(
            repo_root,
            optional_features=["docker"],
            port_mappings=["8080:8080"],
        )

        gen = ComposeGenerator()
        gen.generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert "    ports:" in compose_content
        assert "      - 8080:8080" in compose_content
        assert "seccomp=unconfined" in compose_content


class TestDshConfigGeneration:
    """Tests for dsh .env and compose generation."""

    def test_dsh_env_declares_tool_and_global_keys(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        dsh_dir = tmp_path / ".dsh"
        dsh_dir.mkdir()
        ctx = _make_generation_context(tmp_path, config_dir=dsh_dir, agent_tool="dsh")

        ConfigFilesGenerator().generate(ctx)

        env_content = (dsh_dir / ".env").read_text()
        assert "OCF_AGENT_TOOL=dsh" in env_content
        assert "OCF_GLOBAL_CONFIG_PATH" in env_content
        assert "OCF_GLOBAL_AUTH_PATH" in env_content

    def test_dsh_compose_pins_dsh_home_and_mounts_global_files(self, tmp_path: Path):
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        dsh_dir = repo_root / ".dsh"
        dsh_dir.mkdir()
        ctx = _make_generation_context(repo_root, config_dir=dsh_dir, agent_tool="dsh")

        ComposeGenerator().generate(ctx)

        compose_content = (dsh_dir / "docker-compose.yaml").read_text()
        assert "DSH_HOME=/home/${REMOTE_USER}/.dsh" in compose_content
        assert (
            "- ${OCF_GLOBAL_CONFIG_PATH:-/dev/null}:"
            "/home/${REMOTE_USER}/.dsh/settings.yaml:ro" in compose_content
        )
        assert (
            "- ${OCF_GLOBAL_AUTH_PATH:-/dev/null}:"
            "/home/${REMOTE_USER}/.dsh/.credentials.yaml:ro" in compose_content
        )
        assert 'command: ""' in compose_content

    def test_opencode_compose_keeps_empty_default_command(self, tmp_path: Path):
        """No compose template change for dsh: default command stays empty."""
        repo_root = tmp_path / "myproject"
        repo_root.mkdir()
        opencode_dir = repo_root / ".opencode"
        opencode_dir.mkdir()
        ctx = _make_generation_context(repo_root)

        ComposeGenerator().generate(ctx)

        compose_content = (opencode_dir / "docker-compose.yaml").read_text()
        assert 'command: ""' in compose_content


class TestAuthStubPermissions:
    """The auth fallback stub must be owner-only (dsh enforces 0600)."""

    @staticmethod
    def _framework_repo_with_stub(tmp_path: Path) -> Path:
        framework_repo = tmp_path / "framework"
        stub = framework_repo.joinpath("framework-config", *DSH_TOOL_SPEC.stub_relpath)
        stub.parent.mkdir(parents=True)
        stub.write_text("{}\n")
        stub.chmod(0o644)
        return framework_repo

    def test_stub_hardened_when_wired_as_auth_fallback(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        framework_repo = self._framework_repo_with_stub(tmp_path)
        stub = framework_repo / "framework-config" / "dsh" / "stubs"
        dsh_dir = tmp_path / ".dsh"
        dsh_dir.mkdir()
        ctx = _make_generation_context(
            tmp_path,
            config_dir=dsh_dir,
            agent_tool="dsh",
            global_settings=_make_global_settings(
                framework_repo_path=str(framework_repo)
            ),
        )

        ConfigFilesGenerator().generate(ctx)

        env_content = (dsh_dir / ".env").read_text()
        assert (
            "OCF_GLOBAL_AUTH_PATH=${OCF_LOCAL_FRAMEWORK_PATH}/"
            "framework-config/dsh/stubs/stub-credentials.yaml"
        ) in env_content
        assert (stub / "stub-credentials.yaml").stat().st_mode & 0o777 == 0o600

    def test_existing_host_credentials_left_untouched(
        self, tmp_path: Path, monkeypatch
    ):
        home = tmp_path / "home"
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))
        credentials = home / ".dsh" / ".credentials.yaml"
        credentials.parent.mkdir(parents=True)
        credentials.write_text("providers: {}\n")
        credentials.chmod(0o644)
        framework_repo = self._framework_repo_with_stub(tmp_path)
        stub = framework_repo / "framework-config" / "dsh" / "stubs"
        dsh_dir = tmp_path / ".dsh"
        dsh_dir.mkdir()
        ctx = _make_generation_context(
            tmp_path,
            config_dir=dsh_dir,
            agent_tool="dsh",
            global_settings=_make_global_settings(
                framework_repo_path=str(framework_repo)
            ),
        )

        ConfigFilesGenerator().generate(ctx)

        env_content = (dsh_dir / ".env").read_text()
        assert f"OCF_GLOBAL_AUTH_PATH={credentials}" in env_content
        assert credentials.stat().st_mode & 0o777 == 0o644
        assert (stub / "stub-credentials.yaml").stat().st_mode & 0o777 == 0o644


class TestHostDotfileMirrorRendering:
    """Rendering of the host ~/.npmrc and ~/.m2/settings.xml mirrors."""

    def test_compose_has_npmrc_mount_for_every_tool(self):
        for tool in ("opencode", "qwen", "dsh"):
            content = TemplateHandler.render_compose_template("repo", agent_tool=tool)
            assert NPMRC_MOUNT_LINE in content
            assert (
                "      - ${OCF_NPMRC_PATH:-/dev/null}:/home/${REMOTE_USER}/.npmrc:ro"
            ) in content

    def test_compose_npmrc_mount_without_any_features(self):
        content = TemplateHandler.render_compose_template("repo")
        assert NPMRC_MOUNT_LINE in content

    def test_compose_has_gitconfig_mount_for_every_tool(self):
        for tool in ("opencode", "qwen", "dsh"):
            content = TemplateHandler.render_compose_template("repo", agent_tool=tool)
            assert GITCONFIG_MOUNT_LINE in content
            assert (
                "      - ${OCF_GITCONFIG_PATH:-/dev/null}:"
                "/home/${REMOTE_USER}/.gitconfig:ro"
            ) in content

    def test_compose_gitconfig_mount_without_any_features(self):
        content = TemplateHandler.render_compose_template("repo")
        assert GITCONFIG_MOUNT_LINE in content

    def test_ssh_mount_with_feature_and_host_dir(self, monkeypatch):
        monkeypatch.setattr(
            "opencode_framework.generators.templates.host_ssh_dir_path",
            lambda enabled: "/home/alice/.ssh" if enabled else "",
        )
        content = TemplateHandler.render_compose_template("repo", ["ssh"])
        assert SSH_MOUNT_LINE in content
        assert "      - ${OCF_SSH_DIR_PATH}:/home/${REMOTE_USER}/.ssh:ro" in content

    def test_ssh_mount_omitted_without_feature_or_host_dir(self, monkeypatch):
        monkeypatch.setattr(
            "opencode_framework.generators.templates.host_ssh_dir_path",
            lambda enabled: "/home/alice/.ssh" if enabled else "",
        )
        assert SSH_MOUNT_LINE not in TemplateHandler.render_compose_template("repo")
        monkeypatch.setattr(
            "opencode_framework.generators.templates.host_ssh_dir_path",
            lambda enabled: "",
        )
        assert SSH_MOUNT_LINE not in TemplateHandler.render_compose_template(
            "repo", ["ssh"]
        )

    def test_maven_adds_m2_settings_mount(self):
        content = TemplateHandler.render_compose_template(
            "repo", ["java"], java_build_tools=["maven"]
        )
        assert M2_SETTINGS_MOUNT_LINE in content

    def test_gradle_alone_has_no_m2_settings_mount(self):
        content = TemplateHandler.render_compose_template(
            "repo", ["java"], java_build_tools=["gradle"]
        )
        assert M2_SETTINGS_MOUNT_LINE not in content

    def test_no_m2_settings_mount_without_java(self):
        content = TemplateHandler.render_compose_template("repo", ["python"])
        assert M2_SETTINGS_MOUNT_LINE not in content

    def test_env_renders_mirror_paths_and_gradle(self):
        content = TemplateHandler.render_env_template(
            npmrc_path="/home/alice/.npmrc",
            m2_settings_path="/home/alice/.m2/settings.xml",
            java_build_tools=["maven", "gradle"],
        )
        assert "OCF_NPMRC_PATH=/home/alice/.npmrc" in content
        assert "OCF_M2_SETTINGS_PATH=/home/alice/.m2/settings.xml" in content
        assert 'GRADLE_OPTS="-Dorg.gradle.daemon=false"' in content

    def test_env_mirror_keys_empty_without_host_files(self):
        content = TemplateHandler.render_env_template()
        assert "OCF_NPMRC_PATH=\n" in content
        assert "OCF_M2_SETTINGS_PATH=\n" in content
        assert "OCF_GITCONFIG_PATH=\n" in content
        assert "OCF_SSH_DIR_PATH=\n" in content
        assert "GRADLE_OPTS" not in content

    def test_env_renders_gitconfig_and_ssh_paths(self):
        content = TemplateHandler.render_env_template(
            gitconfig_path="/home/alice/.gitconfig",
            ssh_dir_path="/home/alice/.ssh",
        )
        assert "OCF_GITCONFIG_PATH=/home/alice/.gitconfig" in content
        assert "OCF_SSH_DIR_PATH=/home/alice/.ssh" in content

    def test_env_gradle_opts_only_with_gradle(self):
        content = TemplateHandler.render_env_template(java_build_tools=["maven"])
        assert "GRADLE_OPTS" not in content
        content = TemplateHandler.render_env_template(java_build_tools=["gradle"])
        assert 'GRADLE_OPTS="-Dorg.gradle.daemon=false"' in content

    def test_env_template_fully_resolved(self):
        content = TemplateHandler.render_env_template()
        assert "{{" not in content

    def _generate_env(
        self,
        tmp_path,
        java_build_tools=None,
        agent_tool="opencode",
        optional_features=None,
    ):
        config_dir = (
            tmp_path
            / {
                "opencode": ".opencode",
                "qwen": ".qwen",
                "dsh": ".dsh",
            }[agent_tool]
        )
        config_dir.mkdir(parents=True)
        ctx = _make_generation_context(
            tmp_path,
            config_dir=config_dir,
            agent_tool=agent_tool,
            java_build_tools=java_build_tools or [],
            optional_features=optional_features or [],
        )
        ConfigFilesGenerator().generate(ctx)
        return (config_dir / ".env").read_text()

    def test_init_records_host_npmrc(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        (home / ".npmrc").parent.mkdir(parents=True)
        (home / ".npmrc").write_text("registry=https://example.invalid\n")
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))

        content = self._generate_env(tmp_path)
        assert f"OCF_NPMRC_PATH={home / '.npmrc'}" in content

    def test_init_leaves_npmrc_empty_when_absent(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        content = self._generate_env(tmp_path)
        assert "OCF_NPMRC_PATH=\n" in content

    def test_init_records_m2_settings_only_with_maven(
        self, tmp_path: Path, monkeypatch
    ):
        home = tmp_path / "home"
        (home / ".m2").mkdir(parents=True)
        (home / ".m2" / "settings.xml").write_text("<settings/>\n")
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))

        content = self._generate_env(tmp_path, java_build_tools=["maven"])
        assert f"OCF_M2_SETTINGS_PATH={home / '.m2' / 'settings.xml'}" in content

        gradle_only = self._generate_env(
            tmp_path / "gradle-only", java_build_tools=["gradle"]
        )
        assert "OCF_M2_SETTINGS_PATH=\n" in gradle_only

    def test_init_records_gradle_opts_only_with_gradle(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))

        content = self._generate_env(tmp_path, java_build_tools=["maven", "gradle"])
        assert 'GRADLE_OPTS="-Dorg.gradle.daemon=false"' in content
        assert "GRADLE_OPTS" not in self._generate_env(
            tmp_path / "mv", java_build_tools=["maven"]
        )

    def test_init_records_gitconfig(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        (home / ".gitconfig").write_text("[user]\n\tname = Alice\n")
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))

        content = self._generate_env(tmp_path)
        assert f"OCF_GITCONFIG_PATH={home / '.gitconfig'}" in content

    def test_init_records_ssh_dir_only_with_feature(self, tmp_path: Path, monkeypatch):
        home = tmp_path / "home"
        (home / ".ssh").mkdir(parents=True)
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))

        content = self._generate_env(tmp_path, optional_features=["ssh"])
        assert f"OCF_SSH_DIR_PATH={home / '.ssh'}" in content

        without = self._generate_env(tmp_path / "no-ssh")
        assert "OCF_SSH_DIR_PATH=\n" in without


class TestHostMirrorConfigHelpers:
    """Tests for config.host_npmrc_path / config.host_m2_settings_path."""

    def test_npmrc_path_found_and_missing(self, tmp_path: Path, monkeypatch):
        from opencode_framework import config

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))
        assert config.host_npmrc_path() == ""
        npmrc = home / ".npmrc"
        npmrc.write_text("x=1\n")
        assert config.host_npmrc_path() == str(npmrc)

    def test_m2_settings_requires_maven(self, tmp_path: Path, monkeypatch):
        from opencode_framework import config

        home = tmp_path / "home"
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))
        settings = home / ".m2" / "settings.xml"
        settings.parent.mkdir(parents=True)
        settings.write_text("<settings/>\n")
        assert config.host_m2_settings_path(False) == ""
        assert config.host_m2_settings_path(True) == str(settings)
        settings.unlink()
        assert config.host_m2_settings_path(True) == ""

    def test_gitconfig_path_found_and_missing(self, tmp_path: Path, monkeypatch):
        from opencode_framework import config

        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))
        assert config.host_gitconfig_path() == ""
        gitconfig = home / ".gitconfig"
        gitconfig.write_text("[user]\n")
        assert config.host_gitconfig_path() == str(gitconfig)

    def test_ssh_dir_requires_feature_and_dir(self, tmp_path: Path, monkeypatch):
        from opencode_framework import config

        home = tmp_path / "home"
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(home))
        ssh = home / ".ssh"
        ssh.mkdir(parents=True)
        assert config.host_ssh_dir_path(False) == ""
        assert config.host_ssh_dir_path(True) == str(ssh)

        empty = tmp_path / "empty-home"
        empty.mkdir()
        monkeypatch.setenv("HOME", str(empty))
        assert config.host_ssh_dir_path(True) == ""
