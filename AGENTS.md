# Agent Instructions

Technical details and code conventions for the OpenCode Framework.

**Active plan:** [tool-adoption.md](tool-adoption.md) — configurable agent tool
(`opencode` | `qwen`), 3-part restructure, and env-var taxonomy.
The layout and conventions on this page describe the target state of that plan.

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
├── agent/               # PART 2: agent tool integration
│   ├── registry.py      # ToolSpec registry (opencode | qwen)
│   ├── discovery.py     # Config directory discovery + OCF_AGENT_TOOL cross-check
│   └── layers.py        # .env tool sections, project stubs, stub fallbacks
├── sandbox/             # PART 1: tool-agnostic sandbox
│   ├── devcontainer.py  # devcontainer.json + Dockerfile image build
│   ├── compose.py       # docker-compose generation + reconciliation
│   ├── runtime.py       # Launch environment handling
│   ├── net.py           # Port management
│   └── features.py      # Feature set reconciliation on rebuild
├── cli/
│   ├── __init__.py
│   └── app.py           # Typer CLI commands (init, launch)
├── exceptions/          # Custom exception hierarchy (FrameworkError family)
├── generators/          # Shared generators/assemblers for the active tool's config dir (ctx, templates, env, docs)
├── config.py            # Global settings, framework validation
├── preflight.py         # Preflight checks (git queries come from git_ops)
├── git_ops.py           # Git repository queries + worktree management (single git implementation)
├── wizard.py            # Interactive setup wizard
└── templates/           # Plain-text templates rendered via {{PLACEHOLDER}} replacement
```

Moves from the pre-restructure layout (`generators/devcontainer.py`,
`generators/compose.py`, top-level `runtime.py`/`net.py`/`features.py`/
`devcontainer.py`) are tracked in [tool-adoption.md](tool-adoption.md).

## Build/Lint/Test Commands

```sh
poetry run ruff check .                 # Lint
poetry run ruff format .                # Format code
poetry run mypy opencode_framework/     # Type checking
poetry run pytest                              # Run all tests
poetry run pytest --cov=opencode_framework     # Run with coverage
poetry run pytest tests/test_preflight.py -v   # Run single test file
poetry run pytest tests/ -k "git" -v           # Run tests matching pattern
poetry build                                   # Build package
```

## Code Style Guidelines

### Imports

Import grouping and ordering are enforced by ruff's isort rule (I). Run `ruff check --fix` to auto-fix:

```python
import os
import subprocess
from pathlib import Path
from typing import List, Optional

import typer

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
def run_git_command(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    ...

def validate_runtime_context(cwd: Path, config_dirname: str, repo_root: Optional[Path] = None) -> Tuple[bool, str]:
    ...
```

### Dataclasses

Use dataclasses for structured data with type hints. Use `field(default_factory=...)` for mutable defaults:

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PreflightResult:
    success: bool
    error: Optional[str] = None
    remediation: Optional[str] = None
    missing_tools: List[str] = field(default_factory=list)
```

### Naming Conventions

- **Functions/variables**: `snake_case` (e.g., `run_preflight_checks`, `repo_root`)
- **Classes**: `PascalCase` (e.g., `PreflightResult`, `WorktreeResult`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `REQUIRED_TOOLS`)
- **Private functions**: prefix with `_` (e.g., `_check_framework_repo`)
- **Test classes**: `Test<Feature>` (e.g., `TestCheckRequiredTools`)
- **Test methods**: `test_<behavior>` (e.g., `test_returns_list`)

### Docstrings

Use Google-style docstrings for modules, classes, and public functions:

```python
def ensure_qwen_project_layer(config_dir: Path) -> Optional[Path]:
    """Create the qwen project layer (``<config_dir>/settings.json``) if absent.

    The qwen config worktree root is the native ``.qwen/`` directory, so
    the project settings file sits at the worktree root. Only-if-missing
    by design: an existing file is never overwritten, so ``init --force``
    preserves user edits.

    Args:
        config_dir: qwen config worktree directory (``.qwen/``).

    Returns:
        Path to the created settings file, or None when it already
        existed.
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
FrameworkError (base; carries message, remediation, context)
├── ValidationError
└── PortAllocationError
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

def run_git_command(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a git command; failures and timeouts return non-zero codes."""
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args=["git"] + args, returncode=-1, stdout="", stderr="Git command timed out")
```

### Generator Pattern

File generators extend `FileGenerator` abstract base class and receive a `GenerationContext`:

```python
from opencode_framework.generators.base import FileGenerator, GenerationContext

class DevcontainerGenerator(FileGenerator):
    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer.json in the active tool's config dir."""
        # Access: ctx.repo_root, ctx.config_dir, ctx.agent_tool,
        # ctx.branch_name, etc.
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

### Run after every change

Before considering a task complete, the following commands must all pass:

```sh
poetry run ruff check .      # Check for linting issues
poetry run ruff format .     # Format code
poetry run mypy opencode_framework/   # Check type annotations
poetry run pytest            # Run tests
```

**Note on imports:** Import grouping is now enforced by ruff's isort rule (I). The manual "Imports" section above is superseded — run `ruff check --fix` to auto-fix import order. The 88-char line limit will wrap some existing long lines; expect a moderate formatting diff after running `ruff format`.

## Architecture Essentials

### CLI Contract

- `ocframework init [--tool opencode|qwen]` - Initialize framework in a Git repository
- `ocframework launch [--tool opencode|qwen]` - Launch container with the configured agent
- `ocframework --version` - Print version and configuration status

All commands require a valid framework repository (installed via `pipx install -e <path>`).

Multiple harnesses can coexist in one project — one per tool, each with its own
isolated config directory (`.opencode/`, `.qwen/`), `.env`, container, volumes,
and image tag. `init --tool <name>` adds a harness without touching existing
ones. `launch` detects configured harnesses: one valid config launches directly,
several valid configs prompt for a choice (interactive TTY; hard error with
`--tool` remediation when non-interactive).

Launch target selection precedence: `--tool` flag > auto-detect (exactly one
valid config dir) > interactive prompt (multiple valid, interactive TTY);
non-interactive with multiple valid configs is a hard error. Pass-through
args after `--` go to the agent binary; generated documentation commands
include `--tool <name>` (e.g. `ocframework launch --tool qwen -- debug config`).

### init Preconditions

Fails unless:
- Framework installed as editable from valid git clone
- Current directory is Git repository root
- Repository is not bare
- No staged changes in Git index

### Architecture

The framework separates build and runtime concerns:

1. **DevContainer (Build)** - `devcontainer.json`
   - Defines container image via features
   - Installs tools (Python, Node.js, Docker, etc.)
   - Build output: cached Docker image

2. **Docker Compose (Runtime)** - `docker-compose.yaml`
   - Environment variable injection
   - Bind mounts (project source, config)
   - Named volumes (persistent dependencies)
   - Runtime configuration (user, command, etc.)

This hybrid approach enables:
- Environment propagation from host (DevContainer CLI lacks this)
- Fast container starts without rebuilding
- Persistent dependency caches via named volumes

### Three-Part Architecture

The framework splits into three parts with explicit borders (module names in code, variable prefixes in `.env`, directory structure for content) — see [vision.md](vision.md) and [tool-adoption.md](tool-adoption.md):

1. **Sandbox** (`opencode_framework/sandbox/`) — tool-agnostic isolation: devcontainer image build, compose runtime, mounts, ports. Never imports tool knowledge; renders agent slots only (`{{AGENT_FEATURE}}`, `{{AGENT_INSTALL}}`, `{{AGENT_ENV}}`, `{{AGENT_MOUNTS}}`, `{{SERVICE_NAME}}`/`{{ENTRYPOINT}}`, build args).
2. **Agent integration** (`opencode_framework/agent/`) — `registry.py` holds one ToolSpec per tool (opencode, qwen); `layers.py` wires the config layers global < framework < project (+ env, CLI args).
3. **Nuts-and-bolts** (repo content `framework-nuts-and-bolts/{common,opencode,qwen}/`) — snippet library; `common/` + the active tool's folder are mounted read-only into `.opencode/framework-nuts-and-bolts/`.

### Environment Variable Taxonomy

Rule: variables shared across parts/tools may be unprefixed; part- or tool-specific ones must be prefixed.

| Family | Variables |
|---|---|
| shared (no prefix) | `REMOTE_USER`, `XDG_*` |
| sandbox | `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`, `OCF_REMOTE_FRAMEWORK_CONFIG_PATH` |
| agent tool | `OCF_AGENT_TOOL`, `OCF_AGENT_VERSION` |
| agent layers | `OCF_GLOBAL_CONFIG_PATH` (dir for opencode, file for qwen), `OCF_GLOBAL_AUTH_PATH` (opencode only) |
| agent defaults via env | `OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`, `OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS`, `OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS` |
| tool-native (agent's own contract, never OCF-prefixed) | `OPENCODE_*`, `QWEN_*` |

Renamed keys are not migrated: a `.env` whose `OCF_AGENT_TOOL` is missing or
contradicts its config directory (`.opencode/` = opencode, `.qwen/` = qwen) is
a hard launch error with a re-init remediation — regenerate via
`ocframework init --force --tool <tool>` (existing directory backed up first).

### Git Worktree Model

- The config worktree lives in a per-tool native dir: `.opencode/`
  (opencode) or `.qwen/` (qwen) — a nested linked Git worktree on a
  separate branch
- Branch name suggested: `codeagent-{username}-{tool}` for every tool
  (e.g. `codeagent-alice-opencode`, `codeagent-alice-qwen`); git refuses
  to check out one branch in two worktrees, hence the per-tool mark
- If branch exists, reuse it; otherwise create orphan branch
- Framework never auto-commits; developer controls commits

### Per-Tool Naming

- Containers: `ocf_<repo>_<tool>` (e.g. `ocf_myrepo_qwen`)
- Managed named volumes: `{kind}-{repo}-{tool}` (e.g. `venv-myrepo-qwen`,
  `m2-myrepo-qwen`, `gradle-myrepo-qwen`, `docker-myrepo-qwen`) via
  `managed_volume_name(prefix, repo_name, tool)` in `agent/registry.py` —
  two agents can run concurrently on one repo without sharing mutable state
- Built images: `ocf-<repo>-<tool>:latest` (e.g. `ocf-myrepo-qwen:latest`),
  applied via `devcontainer build --image-name` after the `devcontainer up`
  step; persisted in the tool's `<config_dir>/runtime_data/.image_id` and
  surfaced as `OCF_IMAGE_ID` — avoids collision on the devcontainer CLI's
  shared `vsc-<workspace>-<hash>` tag when several harnesses build for the
  same workspace folder
- Containers created before the per-tool naming upgrade (`ocf_<repo>`) are
  not auto-attached by `launch`; remove them (`docker rm -f ocf_<repo>`)
  or run `launch --force` once

### Security Model

Read-only mounts:
- Framework repository, `framework-config/`, and `framework-nuts-and-bolts/{common,<tool>}/`
- Global layer, per tool: opencode — global config directory (host: `~/.config/opencode`) + auth file (global auth if present, else framework stub); qwen — `~/.qwen/settings.json` (global if present, else framework stub)
- qwen framework settings at `/home/$REMOTE_USER/.qwen/settings.json`

Read-write mounts:
- `<config_dir>/runtime_data/` (`.opencode/runtime_data/` or `.qwen/runtime_data/`)
- Project source repository (including `.qwen/` for qwen)

qwen has no auth file: API keys (`DASHSCOPE_API_KEY`, `OPENAI_API_KEY` + `OPENAI_BASE_URL`) are injected via the env layer.

### Docker-in-Docker Support

When the `docker` optional feature is selected during `ocframework init`:

- The generated `docker-compose.yaml` includes `privileged: true` on the service and an entrypoint of `["/usr/local/share/docker-init.sh", "<agent-binary>"]`
- The container image includes `/etc/docker/daemon.json` with `{"firewall-backend": "nftables"}` (baked in unconditionally — harmless without Docker installed)
- The `docker-in-docker:2` devcontainer feature installs Docker CE and `/usr/local/share/docker-init.sh`
- Docker daemon **starts automatically** on container launch. The container entrypoint runs `/usr/local/share/docker-init.sh` before the agent binary, which starts dockerd with readiness checks.
- Docker autodetects the storage driver: prefers `overlay2` where supported, falls back to `vfs` in sandboxed environments without overlayfs support.
- A named volume `docker-<repo>-<tool>` is mounted at `/var/lib/docker` to persist Docker data across container restarts. If you upgrade the daemon to a version incompatible with this volume, you may need to run `docker volume rm docker-<repo>-<tool>` to recreate it.
