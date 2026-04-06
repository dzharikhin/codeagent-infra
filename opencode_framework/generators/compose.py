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
        
        Args:
            ctx: Generation context with repo_root, optional_features, etc.
        """
        compose_path = ctx.opencode_dir / "docker-compose.yaml"
        compose_content = TemplateHandler.render_compose_template(
            repo_root_name=ctx.repo_root.name,
            optional_features=ctx.optional_features,
        )
        compose_path.write_text(compose_content)
