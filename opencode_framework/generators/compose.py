"""Docker Compose file generation."""

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class ComposeGenerator(FileGenerator):
    """Generates .opencode/docker-compose.yaml for runtime."""
    
    def generate(self, ctx: GenerationContext) -> None:
        """Generate docker-compose.yaml from template.
        
        The template uses environment variable interpolation:
        - PWD: Set at launch time to repo root
        - Other vars: Loaded from .opencode/.env
        """
        compose_path = ctx.opencode_dir / "docker-compose.yaml"
        compose_content = TemplateHandler.render_compose_template(ctx.repo_root.name)
        compose_path.write_text(compose_content)
