"""Configuration file generation (.env, .gitignore)."""

from pathlib import Path

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class ConfigFilesGenerator(FileGenerator):
    """Generates .opencode/.env and .opencode/.gitignore files."""

    def generate(self, ctx: GenerationContext) -> None:
        """Generate all configuration files."""
        self._generate_env_file(ctx)
        self._generate_gitignore(ctx)

    @staticmethod
    def _generate_env_file(ctx: GenerationContext) -> None:
        """Generate .opencode/.env from template.

        Template contains defaults with placeholders for detected paths.
        """
        settings = ctx.global_settings

        if settings.global_auth_found and settings.global_auth_path:
            auth_path = settings.global_auth_path
        elif settings.framework_repo_path:
            framework_path = Path(settings.framework_repo_path)
            stub_auth = framework_path / "framework-nuts-and-bolts" / "stub-auth.json"
            if (framework_path / ".git").is_dir() and stub_auth.is_file():
                auth_path = "${OCF_LOCAL_FRAMEWORK_PATH}/framework-nuts-and-bolts/stub-auth.json"
            else:
                auth_path = ""
        else:
            auth_path = ""

        env_content = TemplateHandler.render_env_template(
            global_config_path=settings.global_config_path,
            global_auth_path=auth_path,
            framework_repo_path=settings.framework_repo_path,
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
