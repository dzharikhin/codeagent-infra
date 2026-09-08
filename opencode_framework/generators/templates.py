"""Template loading and rendering."""

import json
from importlib.resources import files
from typing import Dict, List, Optional

from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    get_tool_spec,
    managed_volume_name,
)

# Per-tool README sections. Each *_SECTION value is a self-contained
# Markdown block ending in a newline; it may embed {{LAUNCH_COMMAND}},
# which resolves on the shared replacement pass afterwards.
_README_SECTIONS: Dict[str, Dict[str, str]] = {
    "opencode": {
        "models": (
            "### Available Models\n"
            "\n"
            "To see available models (including any autodiscovered by the\n"
            "`opencode-models-discovery` plugin), run inside the container:\n"
            "\n"
            "```sh\n"
            "opencode models\n"
            "```\n"
        ),
        "install": (
            "the `opencode` devcontainer feature "
            "(ghcr.io/jsburckhardt/devcontainer-features/opencode), "
            "version-pinned via `OCF_AGENT_VERSION`."
        ),
        "config_layers": (
            "## Configuration Layers\n"
            "\n"
            "Config and env layers, lowest to highest precedence:\n"
            "\n"
            "| Layer | Location |\n"
            "|---|---|\n"
            "| Global | host `~/.config/opencode/` (config dir) and "
            "`~/.local/share/opencode/auth.json` (auth), mounted read-only |\n"
            "| Framework | framework-config mounted at `/opt/ocframework/config` "
            "(`OPENCODE_CONFIG`, `OPENCODE_TUI_CONFIG`) |\n"
            "| Project | this `.opencode/` worktree (`.env`, compose, "
            "nuts-and-bolts) |\n"
        ),
        "serve": (
            "## Run a Headless Server\n"
            "\n"
            "Run the OpenCode server inside the container so external clients "
            "(TUI attach, SDK, IDE, web UI) can connect:\n"
            "\n"
            "```sh\n"
            "{{LAUNCH_COMMAND}} --server\n"
            "```\n"
            "\n"
            "`--server` publishes the server port (container port 4096) and "
            "appends `serve --hostname 0.0.0.0 --port 4096` to the container "
            "command. Pass an explicit host port with `--server=5000`; without "
            "a value a free port is auto-assigned. Compose-configured ports "
            "are republished individually in this mode (`--service-ports` and "
            "`--publish` are mutually exclusive in `docker compose run`). Set "
            "`OPENCODE_SERVER_PASSWORD` in `.env` to enable basic auth.\n"
        ),
        "docs": "- OpenCode docs: https://opencode.ai",
    },
    "qwen": {
        "models": (
            "### Available Models\n"
            "\n"
            "Models are selected via the model stack in `.env` "
            "(`OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`) or in "
            "the qwen settings layers.\n"
        ),
        "install": (
            "Node.js 22 + `npm install -g @qwen-code/qwen-code` in the "
            "Dockerfile, version-pinned via the `OCF_AGENT_VERSION` build arg."
        ),
        "config_layers": (
            "## Configuration Layers\n"
            "\n"
            "Settings layers, lowest to highest precedence (qwen native "
            "scopes):\n"
            "\n"
            "| Layer | Location |\n"
            "|---|---|\n"
            "| Global | host `~/.qwen/settings.json`, injected as "
            "`QWEN_CODE_SYSTEM_DEFAULTS_PATH` |\n"
            "| Framework | framework `qwen-settings.json` mounted at "
            "`~/.qwen/settings.json` in the container |\n"
            "| Project | this `.qwen/` worktree (`settings.json`) |\n"
            "\n"
            "qwen has no auth file: API keys (`DASHSCOPE_API_KEY`, or "
            "`OPENAI_API_KEY` + `OPENAI_BASE_URL`) are provided via the env "
            "layer (`.env` or `launch -e`).\n"
        ),
        "serve": (
            "## Run a Headless Server\n"
            "\n"
            "Run the Qwen Code Web Shell inside the container:\n"
            "\n"
            "```sh\n"
            "{{LAUNCH_COMMAND}} --server\n"
            "```\n"
            "\n"
            "`--server` publishes the Web Shell port (container port 4170), "
            "appends `serve --hostname 0.0.0.0 --port 4170` to the container "
            "command and auto-generates a `QWEN_SERVER_TOKEN`, printed once "
            "at launch (a value set in `.env` or passed via `-e` wins). Pass "
            "an explicit host port with `--server=5000`; without a value a "
            "free port is auto-assigned. Compose-configured ports are "
            "republished individually in this mode. `qwen serve` is "
            "experimental - the TUI remains the stable path.\n"
        ),
        "docs": "- Qwen Code docs: https://github.com/QwenLM/qwen-code",
    },
}


class TemplateHandler:
    """Handles loading and rendering of template files."""

    # Template filenames (without extension)
    DEVCONTAINER_TEMPLATE = "devcontainer.template.json"
    DOCKERFILE_TEMPLATE = "dockerfile.template"
    ENV_TEMPLATE = "env.template"
    COMPOSE_TEMPLATE = "docker-compose.template.yaml"
    README_TEMPLATE = "readme.template.md"
    GITIGNORE_TEMPLATE = "gitignore.template"

    @staticmethod
    def load_json_template(template_name: str) -> dict:
        """Load a JSON template file.

        Args:
            template_name: Name of template file (e.g., "devcontainer.template.json")

        Returns:
            Parsed JSON content as dictionary
        """
        content = (
            files("opencode_framework.templates").joinpath(template_name).read_text()
        )
        return json.loads(content)

    @staticmethod
    def load_text_template(template_name: str) -> str:
        """Load a text template file.

        Args:
            template_name: Name of template file (e.g., "env.template")

        Returns:
            Template content as string
        """
        return files("opencode_framework.templates").joinpath(template_name).read_text()

    @staticmethod
    def render_template(template: str, variables: Dict[str, str]) -> str:
        """Render template with variable substitution.

        Replaces {{VARIABLE}} placeholders with values from variables dict.
        Variables dict keys should include the full {{VARIABLE}} syntax.

        Args:
            template: Template string with {{VARIABLE}} placeholders
            variables: Dictionary mapping full placeholders (with braces) to values

        Returns:
            Rendered template with substitutions applied
        """
        result = template

        # Replace all {{VARIABLE}} patterns
        for placeholder, value in variables.items():
            result = result.replace(placeholder, value)

        return result

    @classmethod
    def load_devcontainer_template(cls) -> dict:
        """Load devcontainer template.

        Returns:
            Parsed devcontainer.json template
        """
        return cls.load_json_template(cls.DEVCONTAINER_TEMPLATE)

    @classmethod
    def load_dockerfile_template(cls) -> str:
        """Load Dockerfile template.

        Returns:
            Dockerfile template content
        """
        return cls.load_text_template(cls.DOCKERFILE_TEMPLATE)

    @classmethod
    def load_env_template(cls) -> str:
        """Load environment template.

        Returns:
            Environment template content
        """
        return cls.load_text_template(cls.ENV_TEMPLATE)

    @classmethod
    def load_compose_template(cls) -> str:
        """Load docker-compose template.

        Returns:
            Docker compose template content
        """
        return cls.load_text_template(cls.COMPOSE_TEMPLATE)

    @classmethod
    def load_readme_template(cls) -> str:
        """Load README template.

        Returns:
            README template content
        """
        return cls.load_text_template(cls.README_TEMPLATE)

    @classmethod
    def render_env_template(
        cls,
        global_config_path: Optional[str] = None,
        global_auth_path: Optional[str] = None,
        framework_repo_path: Optional[str] = None,
        agent_tool: str = DEFAULT_TOOL,
    ) -> str:
        """Render environment template with paths and the tool fragment.

        Args:
            global_config_path: Path to the global config layer (dir or file)
            global_auth_path: Path to the global auth file (opencode only)
            framework_repo_path: Path to framework repository
            agent_tool: Agent tool name ("opencode" | "qwen")

        Returns:
            Rendered environment template
        """
        template = cls.load_env_template()
        spec = get_tool_spec(agent_tool)

        replacements = {
            "{{AGENT_ENV_TEMPLATE}}": spec.env_template_fragment,
            "{{OCF_GLOBAL_CONFIG_PATH}}": global_config_path or "",
            "{{OCF_GLOBAL_AUTH_PATH}}": global_auth_path or "",
            "{{OCF_LOCAL_FRAMEWORK_PATH}}": framework_repo_path or "",
        }

        return cls.render_template(template, replacements)

    @classmethod
    def render_compose_template(
        cls,
        repo_root_name: str,
        optional_features: Optional[List[str]] = None,
        port_mappings: Optional[List[str]] = None,
        java_build_tools: Optional[List[str]] = None,
        agent_tool: str = DEFAULT_TOOL,
    ) -> str:
        """Render docker-compose template for the configured agent tool.

        Service name, entrypoint binary and the agent env/mount blocks
        come from the tool spec; everything else is tool-agnostic sandbox.

        Args:
            repo_root_name: Name of the repo
            optional_features: List of enabled optional features (e.g., ["python"])
            port_mappings: List of Docker-style port mappings (e.g. ["8080:8080"])
            java_build_tools: Enabled Java build tools (e.g., ["maven"], ["gradle"]).
                Empty/None mounts no build-tool volumes.
            agent_tool: Agent tool name ("opencode" | "qwen")

        Returns:
            Rendered docker-compose content
        """
        template = cls.load_compose_template()
        spec = get_tool_spec(agent_tool)
        repo_name = repo_root_name
        tool = spec.name

        additional_volume_mounts = ""
        docker_privileged = ""
        entrypoint = f'["{spec.binary}"]'

        if optional_features and "python" in optional_features:
            additional_volume_mounts += (
                f"\n      - {managed_volume_name('venv', repo_name, tool)}:"
                f"/{repo_name}/.venv"
            )

        # Java build tools: maven or gradle, or both
        if optional_features and "java" in optional_features:
            tools = java_build_tools or []
            if "maven" in tools:
                additional_volume_mounts += (
                    f"\n      - {managed_volume_name('m2', repo_name, tool)}:"
                    f"/home/${{REMOTE_USER}}/.m2"
                )
            if "gradle" in tools:
                additional_volume_mounts += (
                    f"\n      - {managed_volume_name('gradle', repo_name, tool)}:"
                    f"/home/${{REMOTE_USER}}/.gradle"
                )

        if optional_features and "docker" in optional_features:
            docker_privileged = "    privileged: true\n"
            entrypoint = f'["/usr/local/share/docker-init.sh", "{spec.binary}"]'
            additional_volume_mounts += (
                f"\n      - {managed_volume_name('docker', repo_name, tool)}:"
                f"/var/lib/docker"
            )

        volume_keys = []
        if optional_features and "python" in optional_features:
            volume_keys.append(f"  {managed_volume_name('venv', repo_name, tool)}:")
        if optional_features and "docker" in optional_features:
            volume_keys.append(f"  {managed_volume_name('docker', repo_name, tool)}:")
        if optional_features and "java" in optional_features:
            tools = java_build_tools or []
            if "maven" in tools:
                volume_keys.append(f"  {managed_volume_name('m2', repo_name, tool)}:")
            if "gradle" in tools:
                volume_keys.append(
                    f"  {managed_volume_name('gradle', repo_name, tool)}:"
                )

        top_level_volumes_section = ""
        if volume_keys:
            top_level_volumes_section = "\nvolumes:\n" + "\n".join(volume_keys) + "\n"

        ports_section = ""
        if port_mappings:
            port_lines = "".join(f"      - {p}\n" for p in port_mappings)
            ports_section = f"    ports:\n{port_lines}"

        replacements = {
            # Agent fragments first: they contain {{OCF_REPO_ROOT_NAME}}
            # which the later pass must still resolve.
            "{{SERVICE_NAME}}": spec.name,
            "{{OCF_CONFIG_DIR}}": spec.config_dirname,
            "{{AGENT_ENV}}": spec.compose_env_fragment,
            "{{AGENT_MOUNTS}}": spec.compose_mount_fragment,
            "{{OCF_REPO_ROOT_NAME}}": repo_root_name,
            "{{ADDITIONAL_VOLUME_MOUNTS}}": additional_volume_mounts,
            "{{TOP_LEVEL_VOLUMES_SECTION}}": top_level_volumes_section,
            "{{DOCKER_PRIVILEGED}}": docker_privileged,
            "{{PORTS_SECTION}}": ports_section,
            "{{ENTRYPOINT}}": entrypoint,
        }

        return cls.render_template(template, replacements)

    @classmethod
    def render_readme_template(
        cls,
        launch_command: str,
        debug_command: str,
        shell_command: str,
        branch_name: str,
        agent_tool: str = DEFAULT_TOOL,
    ) -> str:
        """Render README template for the configured agent tool.

        Tool-specific sections (models, install, config layers, serve,
        docs link) come from the per-tool section map; everything else
        is shared.

        Args:
            launch_command: CLI launch command
            debug_command: CLI debug command
            shell_command: CLI shell command
            branch_name: Git branch name for config worktree
            agent_tool: Agent tool name ("opencode" | "qwen")

        Returns:
            Rendered README content
        """
        template = cls.load_readme_template()
        spec = get_tool_spec(agent_tool)
        sections = _README_SECTIONS[spec.name]

        replacements = {
            # Tool sections first: their text embeds {{LAUNCH_COMMAND}},
            # which the later pass must still resolve.
            "{{AGENT_MODELS_SECTION}}": sections["models"],
            "{{AGENT_INSTALL_LINE}}": sections["install"],
            "{{AGENT_CONFIG_LAYERS_SECTION}}": sections["config_layers"],
            "{{AGENT_SERVE_SECTION}}": sections["serve"],
            "{{AGENT_DOCS_LINE}}": sections["docs"],
            "{{LAUNCH_COMMAND}}": launch_command,
            "{{DEBUG_COMMAND}}": debug_command,
            "{{SHELL_COMMAND}}": shell_command,
            "{{BRANCH_NAME}}": branch_name,
            "{{CONFIG_DIR}}": spec.config_dirname,
        }

        return cls.render_template(template, replacements)
