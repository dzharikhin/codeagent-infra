"""Documentation file generation (README, etc)."""

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class DocumentationGenerator(FileGenerator):
    """Generates .opencode/README.md."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate documentation."""
        self._generate_readme(ctx)

    @staticmethod
    def _get_launch_commands() -> dict:
        """Get the host-side commands.

        Returns CLI commands that handle environment loading and Docker context.
        """
        return {
            "launch": "ocframework launch",
            "debug": "ocframework launch -- debug config",
            "shell": "docker exec -it <container_name> /bin/bash",
        }

    @staticmethod
    def _generate_readme(ctx: GenerationContext) -> None:
        """Generate .opencode/README.md."""
        commands = DocumentationGenerator._get_launch_commands()

        readme_content = TemplateHandler.render_readme_template(
            launch_command=commands["launch"],
            debug_command=commands["debug"],
            shell_command=commands["shell"],
            branch_name=ctx.branch_name,
        )

        readme_path = ctx.opencode_dir / "README.md"
        readme_path.write_text(readme_content)
