# Agent Instructions

Technical details and code conventions for the OpenCode Framework.

## Setup

```sh
poetry install                    # Create .venv and install dependencies
source .venv/bin/activate         # Activate virtual environment
poetry run ocframework  # Run CLI
```

## Build/Lint/Test Commands

```sh
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=opencode_framework tests/

# Run a single test file
poetry run pytest tests/test_preflight.py -v

# Run a single test class
poetry run pytest tests/test_preflight.py::TestCheckRequiredTools -v

# Run a single test method
poetry run pytest tests/test_preflight.py::TestCheckRequiredTools::test_returns_list -v

# Run tests matching a pattern
poetry run pytest tests/ -k "git" -v

# Type checking (if mypy installed)
poetry run mypy opencode_framework/

# Build package
poetry build
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

```python
def run_command(args: List[str], cwd: Optional[Path] = None) -> GitResult:
    ...

@dataclass
class PreflightResult:
    success: bool
    error: Optional[str] = None
    missing_tools: List[str] = field(default_factory=list)
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

Use custom exceptions from `opencode_framework.exceptions`:

```python
from opencode_framework.exceptions import FrameworkError, ValidationError

# Base exception includes remediation guidance
class FrameworkError(Exception):
    def __init__(self, message: str, remediation: str = None, context: dict = None):
        ...

# Usage
raise ValidationError(
    message="Invalid configuration",
    remediation="Run 'ocframework init' to regenerate config",
    context={"path": str(config_path)}
)
```

Exception hierarchy:
- `FrameworkError` (base) → `ValidationError`, `GitError`, `RuntimeError`, `GenerationError`
- `GitError` → `WorktreeError`
- `RuntimeError` → `EnvError`

### Testing Conventions

- Organize tests in classes by feature: `class TestCheckRequiredTools:`
- Use descriptive test names: `test_fails_outside_git_repo`
- Use `tmp_path` fixture for filesystem operations
- Skip tests when prerequisites unavailable: `pytest.skip("Required tools missing")`

```python
class TestGitOperations:
    """Tests for Git-related preflight functions."""
    
    def test_is_inside_git_tree_true(self, tmp_path: Path):
        """Should return True when inside a git tree."""
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
