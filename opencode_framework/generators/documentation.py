"""Documentation file generation (README, etc)."""

from opencode_framework.agent.registry import get_tool_spec

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class DocumentationGenerator(FileGenerator):
    """Generates the config worktree's README.md."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate documentation."""
        self._generate_readme(ctx)

    @staticmethod
    def _get_launch_commands(agent_tool: str) -> dict:
        """Get the host-side commands for the selected tool.

        Returns CLI commands that handle environment loading and Docker context.
        """
        spec = get_tool_spec(agent_tool)
        return {
            "launch": f"ocframework launch --tool {spec.name}",
            "debug": f"ocframework launch --tool {spec.name} -- debug config",
            "shell": "docker exec -it <container_name> /bin/bash",
        }

    @staticmethod
    def _generate_readme(ctx: GenerationContext) -> None:
        """Generate the config worktree's README.md."""
        commands = DocumentationGenerator._get_launch_commands(ctx.agent_tool)

        readme_content = TemplateHandler.render_readme_template(
            launch_command=commands["launch"],
            debug_command=commands["debug"],
            shell_command=commands["shell"],
            branch_name=ctx.branch_name,
            agent_tool=ctx.agent_tool,
        )

        readme_path = ctx.config_dir / "README.md"
        readme_path.write_text(readme_content)
