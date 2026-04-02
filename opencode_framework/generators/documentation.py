"""Documentation file generation (README, etc)."""

from .base import FileGenerator, GenerationContext


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
            "debug": "ocframework exec -- opencode debug config",
            "shell": "ocframework exec -- bash",
        }
    
    @staticmethod
    def _generate_readme(ctx: GenerationContext) -> None:
        """Generate .opencode/README.md."""
        commands = DocumentationGenerator._get_launch_commands()
        
        readme_content = f"""# OpenCode Framework Configuration

This directory contains the project-level configuration for the OpenCode Framework.

## Structure

- `devcontainer.json` - DevContainer build configuration (image, features)
- `docker-compose.yaml` - Runtime configuration (env, mounts, command)
- `.env` - Runtime environment variables
- `runtime_data/` - Mutable runtime state (not versioned)

## Commands

### Launch

```sh
{commands['launch']}
```

### Debug

```sh
{commands['debug']}
```

### Shell

```sh
{commands['shell']}
```

## How It Works

1. `devcontainer build` creates the container image with features
2. `docker compose run` starts OpenCode with resolved environment and mounts
3. Each `exec` creates a fresh container with the same configuration

## Rebuilding

To rebuild the image (e.g., after changing features):

```sh
ocframework launch --rebuild
```

## Version Control

This directory is a linked Git worktree on branch `{ctx.branch_name}`.

To save configuration changes:
1. `cd .opencode`
2. `git add . && git commit -m "Update config"`
3. `git push origin {ctx.branch_name}`

The `.opencode/` directory is a linked Git worktree. Git commands must run
from inside `.opencode/` to affect the configuration branch.

## Documentation

- Framework docs: https://github.com/dzharikhin/codeagent-infra
- OpenCode docs: https://opencode.ai
"""
        
        readme_path = ctx.opencode_dir / "README.md"
        readme_path.write_text(readme_content)
