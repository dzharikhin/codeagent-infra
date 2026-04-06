# Agent Instructions

Technical details and code conventions for the OpenCode Framework.

## Setup

```sh
poetry install                    # Create .venv and install dependencies
source .venv/bin/activate         # Activate virtual environment
poetry run ocframework            # Run CLI
```

## Project Structure

```
opencode_framework/
├── __init__.py          # Package init, version
├── __main__.py          # Entry point for python -m
├── cli/
│   ├── __init__.py
│   ├── app.py           # Typer CLI commands (init, launch)
│   └── error_handler.py # CLI error handling
├── core/
│   ├── __init__.py
│   ├── config.py        # Configuration discovery
│   └── git.py           # Git operations
├── exceptions/          # Custom exception hierarchy
├── generators/          # File generators for .opencode/
├── models/              # Data models (results, etc.)
├── services/            # Validation services
├── config.py            # Global settings, framework validation
├── preflight.py         # Preflight checks
├── git_ops.py           # Worktree management
├── runtime.py           # Launch environment handling
├── wizard.py            # Interactive setup wizard
└── templates/           # Jinja2 templates
```

## Build/Lint/Test Commands

```sh
poetry run pytest                              # Run all tests
poetry run pytest --cov=opencode_framework     # Run with coverage
poetry run pytest tests/test_preflight.py -v   # Run single test file
poetry run pytest tests/ -k "git" -v           # Run tests matching pattern
poetry run mypy opencode_framework/            # Type checking
poetry build                                   # Build package
```

## Code Style Guidelines

### Imports

Group imports with blank lines between:
1. Standard library (alphabetical)
2. Third-party packages (alphabetical)
3. Local imports (alphabetical)

```python
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer
from pydantic import BaseModel

from opencode_framework.config import GlobalSettings
from opencode_framework.exceptions import FrameworkError
```

### Type Annotations

- Use `typing` module for type hints: `List`, `Optional`, `Dict`, `Tuple`
- Use dataclasses for data models with `@dataclass` decorator
- Use `Path` from pathlib for file paths (not strings)
- Always annotate function parameters and return types
- Common return pattern: `Tuple[bool, List[str]]` for validation results

```python
def run_command(args: List[str], cwd: Optional[Path] = None) -> GitResult:
    ...

def validate_framework_repo(path: Path) -> Tuple[bool, List[str]]:
    ...
```

### Dataclasses

Use dataclasses for structured data with type hints. Use `__post_init__` for default mutable fields:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PreflightResult:
    success: bool
    error: Optional[str] = None
    missing_tools: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.missing_tools is None:
            self.missing_tools = []
```

### Naming Conventions

- **Functions/variables**: `snake_case` (e.g., `run_preflight_checks`, `repo_root`)
- **Classes**: `PascalCase` (e.g., `PreflightResult`, `GitOperations`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `REQUIRED_TOOLS`)
- **Private functions**: prefix with `_` (e.g., `_check_framework_repo`)
- **Test classes**: `Test<Feature>` (e.g., `TestCheckRequiredTools`)
- **Test methods**: `test_<behavior>` (e.g., `test_returns_list`)

### Docstrings

Use Google-style docstrings for modules, classes, and public functions:

```python
def validate_framework_repo(path: Path) -> Tuple[bool, List[str]]:
    """Validate that a path is a valid framework repository.
    
    Checks for required paths:
    - .git/
    - framework-nuts-and-bolts/
    - framework-config/
    
    Args:
        path: Path to validate
        
    Returns:
        Tuple of (is_valid, list_of_missing_paths)
    """
```

### Error Handling

Use custom exceptions from `opencode_framework.exceptions`. All framework exceptions include `message`, `remediation`, and `context` attributes:

```python
from opencode_framework.exceptions import FrameworkError, ValidationError

raise ValidationError(
    message="Invalid configuration",
    remediation="Run 'ocframework init' to regenerate config",
    context={"path": str(config_path)}
)
```

#### Exception Hierarchy

```
FrameworkError (base)
├── ConfigurationError
├── ValidationError
│   ├── ProjectSetupError
│   ├── FrameworkInstallationError
│   ├── EnvironmentError
│   ├── GitRepositoryError
│   └── DirectoryStructureError
├── GitError
│   └── WorktreeError
├── RuntimeError
│   └── EnvError
├── GenerationError
│   ├── TemplateError
│   │   ├── TemplateNotFoundError
│   │   └── TemplateRenderError
│   ├── DevcontainerGenerationError
│   └── ConfigGenerationError
├── PreflighjError      # Note: typo exists in codebase
└── WizardError
```

Note: `runtime.py` defines a separate `EnvError` class for environment loading errors.

### CLI Patterns

Use Typer for CLI commands. Handle errors with `typer.Exit()` and color output with `typer.secho()`:

```python
import typer

@app.command()
def init(
    force: bool = typer.Option(False, "--force", "-f", help="Force regeneration"),
) -> None:
    """Initialize the framework in a Git repository."""
    result = run_preflight_checks(Path.cwd(), force=force)
    
    if not result.success:
        typer.secho(f"Error: {result.error}", fg=typer.colors.RED, err=True)
        if result.remediation:
            typer.secho(f"Remediation: {result.remediation}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    
    typer.secho("Success!", fg=typer.colors.GREEN)
```

### Subprocess Patterns

Use `subprocess.run()` with `capture_output=True`, `text=True`, and timeout:

```python
import subprocess
from typing import List, Optional
from pathlib import Path

def run_git_command(args: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return -1, "", str(e)
```

### Generator Pattern

File generators extend `FileGenerator` abstract base class and receive a `GenerationContext`:

```python
from opencode_framework.generators.base import FileGenerator, GenerationContext

class DevcontainerGenerator(FileGenerator):
    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer.json in .opencode/."""
        # Access: ctx.repo_root, ctx.opencode_dir, ctx.branch_name, etc.
        ...
```

### Testing Conventions

- Organize tests in classes by feature: `class TestCheckRequiredTools:`
- Use descriptive test names: `test_fails_outside_git_repo`
- Use `tmp_path` fixture for filesystem operations
- Use `monkeypatch` fixture for environment variable mocking
- Skip tests when prerequisites unavailable: `pytest.skip("Required tools missing")`

```python
class TestGitOperations:
    """Tests for Git-related preflight functions."""
    
    def test_is_inside_git_tree_true(self, tmp_path: Path):
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        assert is_inside_git_tree(tmp_path) is True
```

## Architecture Essentials

### CLI Contract

- `ocframework init` - Initialize framework in a Git repository
- `ocframework launch` - Launch container with OpenCode agent
- `ocframework --version` - Print version and configuration status

All commands require a valid framework repository (installed via `pipx install -e <path>`).

### init Preconditions

Fails unless:
- Framework installed as editable from valid git clone
- Current directory is Git repository root
- Repository is not bare
- No staged changes in Git index

### Git Worktree Model

- `.opencode/` is a nested linked Git worktree on a separate branch
- Branch name suggested: `codeagent-{username}`
- If branch exists, reuse it; otherwise create orphan branch
- Framework never auto-commits; developer controls commits

### Security Model

Read-only mounts:
- Global config directory (host: `~/.config/opencode`)
- Framework repository and config
- Auth file: global auth if present, else framework stub auth

Read-write mounts:
- `.opencode/runtime_data/`
- Project source repository
