"""Configuration file generation (.env, .gitignore)."""

from pathlib import Path
from typing import Optional

from opencode_framework.agent.layers import discover_global_layer, ensure_project_layer
from opencode_framework.agent.registry import ToolSpec, get_tool_spec

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


def _stub_reference(spec: ToolSpec, stub_path: Optional[str]) -> Optional[str]:
    """Build the .env stub reference for a tool's fallback layer.

    Args:
        spec: Tool spec providing the stub location
        stub_path: Absolute framework stub path, when a framework repo
            is known

    Returns:
        ${OCF_LOCAL_FRAMEWORK_PATH}-based reference when the stub file
        exists, else None
    """
    if not stub_path or not Path(stub_path).is_file():
        return None
    rel = "/".join(("framework-config", *spec.stub_relpath))
    return f"${{OCF_LOCAL_FRAMEWORK_PATH}}/{rel}"


class ConfigFilesGenerator(FileGenerator):
    """Generates .opencode/.env and .opencode/.gitignore files."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate all configuration files."""
        self._generate_env_file(ctx)
        self._generate_gitignore(ctx)
        ensure_project_layer(get_tool_spec(ctx.agent_tool), ctx.repo_root)

    @staticmethod
    def _generate_env_file(ctx: GenerationContext) -> None:
        """Generate .opencode/.env from template.

        Template contains defaults with placeholders; global-layer paths
        are resolved per the tool spec (dir + auth for opencode, settings
        file for qwen) with framework stub fallback.
        """
        settings = ctx.global_settings
        spec = get_tool_spec(ctx.agent_tool)

        layer = discover_global_layer(
            spec, framework_repo_path=settings.framework_repo_path
        )
        stub_ref = _stub_reference(spec, layer.stub_path)

        global_config_path = layer.global_path
        global_auth_path: Optional[str] = None
        if spec.auth_relpath is not None:
            global_auth_path = layer.auth_path or stub_ref
        elif global_config_path is None:
            global_config_path = stub_ref

        env_content = TemplateHandler.render_env_template(
            global_config_path=global_config_path or "",
            global_auth_path=global_auth_path or "",
            framework_repo_path=settings.framework_repo_path,
            agent_tool=ctx.agent_tool,
        )

        if ctx.editor_choice != "none":
            env_content += f"\nEDITOR={ctx.editor_choice}"

        env_path = ctx.opencode_dir / ".env"
        env_path.write_text(env_content)

    @staticmethod
    def _generate_gitignore(ctx: GenerationContext) -> None:
        """Generate .opencode/.gitignore."""
        gitignore_content = """# Runtime data - not intended for versioning
runtime_data/

# Node modules (created by bun install for OpenCode plugins)
node_modules/

# Local overrides
.env.local
*.local.json
"""

        gitignore_path = ctx.opencode_dir / ".gitignore"
        gitignore_path.write_text(gitignore_content)
