"""Documentation file generation (README, etc)."""

from .base import FileGenerator, GenerationContext


class DocumentationGenerator(FileGenerator):
    """Generates .opencode/README.md and runtime_data directory."""
    
    def generate(self, ctx: GenerationContext) -> None:
        """Generate documentation and runtime data structure."""
        self._generate_readme(ctx)
        self._generate_runtime_data(ctx)
    
    @staticmethod
    def _get_launch_commands() -> dict:
        """Get the host-side devcontainer commands.
        
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

- `devcontainer.json` - DevContainer configuration for the agent runtime
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

OpenCode is started on attach via `postAttachCommand` in devcontainer.json.

## Teardown

There is no `devcontainer down` flow yet. To stop and remove the container:

```sh
docker rm -f $(basename "$(pwd)")
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
    
    @staticmethod
    def _generate_runtime_data(ctx: GenerationContext) -> None:
        """Create .opencode/runtime_data/ directory structure.
        
        Only creates XDG-backed directories that are actually mounted:
        - .cache/
        - .local/share/
        - .local/state/
        """
        runtime_data = ctx.opencode_dir / "runtime_data"
        runtime_data.mkdir(exist_ok=True)
        
        subdirs = [
            ".cache",
            ".local/share",
            ".local/state",
        ]
        
        for subdir in subdirs:
            dir_path = runtime_data / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
