# Agent Instructions

This document consolidates all technical details, CLI contracts, and implementation rules for code agents working on this framework.

## Installation Requirement

The framework MUST be installed as an editable package from a git clone:

```sh
pipx install -e <path-to-framework-git-clone>
```

This is the only supported installation method. The framework repository is a required runtime asset, not just a development convenience. All framework commands fail immediately if the framework repository is not a valid git clone with all required files.

## Development Environment Setup

### Project Virtual Environment

The framework uses Python virtual environment for development and testing. The project virtual environment is located at `.venv` in the repository root.

### Poetry Dependency Management

**Poetry is required for development** and is used to manage all project dependencies and virtual environments.

#### Installation

```sh
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -
export PATH="$HOME/.local/bin:$PATH"

# Verify installation
poetry --version
```

#### Initial Setup

```sh
# Clone the repository
git clone <repository-url>
cd opencode_framework

# Install dependencies and create .venv
poetry install

# Activate the virtual environment
source .venv/bin/activate
# Or on Windows:
# .venv\Scripts\activate
```

#### Virtual Environment Management with Poetry

##### Creating/Updating the Virtual Environment

```sh
# Create or update the virtual environment with all dependencies
poetry install

# Install in development mode (includes dev dependencies like pytest)
poetry install --with dev
```

##### Installing Additional Dependencies

```sh
# Add a new runtime dependency
poetry add <package-name>

# Add a development-only dependency
poetry add --group dev <package-name>

# Example: Adding a development dependency
poetry add --group dev pytest pytest-cov
```

##### Updating Dependencies

```sh
# Update all dependencies to latest compatible versions
poetry update

# Update specific package
poetry update <package-name>

# Show current dependency tree
poetry show --tree
```

##### Running Commands in Virtual Environment

```sh
# Run Python in the virtual environment
poetry run python <script.py>

# Run installed CLI tools
poetry run ocframework init

# Run tests
poetry run pytest tests/

# Run linting
poetry run black opencode_framework/
poetry run ruff check opencode_framework/
```

##### Entering the Virtual Environment

```sh
# Activate the virtual environment (shell-specific)
source .venv/bin/activate    # Linux/Mac
.\.venv\Scripts\activate     # Windows PowerShell

# Once activated, run commands directly without 'poetry run'
python script.py
pytest tests/
ocframework --version
```

### Virtual Environment Location

The virtual environment is stored at `.venv` in the repository root:

```
opencode_framework/
├── .venv/                    # Virtual environment (gitignored)
│   ├── bin/                  # Executable scripts
│   ├── lib/                  # Python packages
│   └── pyvenv.cfg           # Venv configuration
├── opencode_framework/       # Source code
├── tests/                    # Test suite
├── pyproject.toml           # Poetry project configuration
└── poetry.lock              # Locked dependency versions
```

### Dependency Configuration

Dependencies are defined in `pyproject.toml`:

```toml
[tool.poetry.dependencies]
python = "^3.12"
typer = "^0.12"              # CLI framework
python-dotenv = "^1.0"       # Environment file parsing
# ... other runtime dependencies

[tool.poetry.group.dev.dependencies]
pytest = "^7.0"              # Testing framework
pytest-cov = "^4.0"          # Coverage reporting
# ... other development dependencies
```

#### Updating Dependencies

When `pyproject.toml` is modified:
1. Poetry automatically updates `.venv` on `poetry install`
2. `poetry.lock` captures exact versions (commit to git)
3. Other developers run `poetry install` to sync their environment

### Development Workflow

#### Before Starting Work

```sh
# Clone and setup
git clone <repository-url>
cd opencode_framework

# Create virtual environment and install dependencies
poetry install

# Activate virtual environment
source .venv/bin/activate
```

#### Running Tests

```sh
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=opencode_framework tests/

# Run specific test file
poetry run pytest tests/test_runtime.py

# Run with verbose output
poetry run pytest -v
```

#### Running the Framework

```sh
# Run with poetry
poetry run ocframework --version
poetry run ocframework init

# Or after activating venv
source .venv/bin/activate
ocframework init
```

#### Code Quality Checks

```sh
# Format code
poetry run black opencode_framework/ tests/

# Lint code
poetry run ruff check opencode_framework/

# Type checking (if mypy is installed)
poetry run mypy opencode_framework/
```

### Troubleshooting

#### Virtual Environment Issues

```sh
# Remove and recreate virtual environment
rm -rf .venv
poetry install

# Clear Poetry cache (if experiencing dependency issues)
poetry cache clear . --all
poetry install
```

#### Dependency Conflicts

```sh
# Show detailed dependency information
poetry show --tree

# Check for outdated packages
poetry update --dry-run

# Update to latest versions (carefully)
poetry update
```

#### Poetry Installation Issues

```sh
# Verify Poetry installation
poetry --version

# Update Poetry to latest version
poetry self update

# Check Poetry configuration
poetry config --list
```

### CI/CD and Poetry

In CI/CD environments:
- Poetry uses `poetry.lock` to ensure reproducible builds
- `.venv` is created fresh in each CI run
- No virtual environment is committed to git

### Important Notes

- **Always commit `poetry.lock`** to version control for reproducible builds
- **Never commit `.venv`** directory (it's in .gitignore)
- **Use `poetry add`** for new dependencies, not manual `pip install`
- **Run `poetry install`** after pulling changes that modify dependencies
- The virtual environment is automatically created at `.venv` by Poetry
- All development should happen within the Poetry-managed virtual environment

## Framework Repository Requirements

A valid framework repository must contain:
- `.git/` directory
- `framework-nuts-and-bolts/` directory
- `framework-nuts-and-bolts/stub-auth.json` file
- `framework-config/` directory

If any required path is missing, the framework will not function.

## CLI Contract

### Commands

- `init` - initialize framework in a Git repository
- `version` (via `--version` or bare command) - print version info

Both commands require a valid framework repository. If missing or invalid, all commands fail immediately with a clear error message.

### init Preconditions

`init` must fail unless all of the following are true:
- framework is installed as editable from a valid git clone
- current directory is inside a Git working tree
- current directory is the repository root
- repository is not bare
- Git index has no staged changes

The following are not checked in v1:
- repo has commits
- repo has remote
- unstaged changes in the working tree
- untracked files
- detached HEAD

### init Flow

1. check required external tools
2. validate framework repository
3. validate current directory as a target repo
4. validate Git index has no staged changes
5. resolve framework repo location from the installed tool
6. autodetect global settings at canonical paths
7. inspect standard devcontainer files, if any
8. inspect whether `.opencode/` already exists
9. ask wizard questions
10. create or reuse the config branch and nested worktree at `.opencode/`
11. generate `.opencode/` contents
12. print launch instructions

### Required Tool Checks

Hard prerequisites:
- `git`
- `docker`
- `devcontainer` (from `@devcontainers/cli`)
- `pipx`

Missing tools cause immediate failure with remediation instructions.

### Version Output

`version` prints:
- framework version
- detected framework repo path (or INVALID marker)
- global config found status and path (if found) or expected path (if not found)
- global auth.json found status and path (if found) or expected path (if not found)

## Global Settings Discovery

The framework discovers global settings in the **local user context** on the host machine, not in the container context.

### Local Context Resolution

Paths are resolved using this precedence:
1. `XDG_CONFIG_HOME` environment variable (if set)
2. `SUDO_USER`'s home directory (if running under sudo)
3. `HOME` environment variable
4. Current process user's home

This ensures that when running `ocframework init` as root or via sudo, the framework still operates in the actual user's context (e.g., `/home/user/.config/opencode` rather than `/root/.config/opencode`).

### Canonical Paths

- `$XDG_CONFIG_HOME/opencode` or `~/.config/opencode` - global config directory (host)
- `$XDG_DATA_HOME/opencode/auth.json` or `~/.local/share/opencode/auth.json` - global auth file (host)

### Global Config Creation Prompt

**This is the first wizard question** if the global config directory does not exist.

If the directory does not exist, `init` prompts immediately:
- "Global config directory not found at: <path>"
- "Create global config directory? [Y/n]"

If accepted, the directory is created in the local user's context before any other setup steps.
If declined, no global config mount is added to `devcontainer.json`.

### Remote/Container Paths

The devcontainer uses separate paths for the container environment:
- `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, etc. in `.opencode/.env` define container-side paths
- These are independent of the host-side discovery paths
- `REMOTE_USER` in `.env` controls the container user (default: `root`)

## Wizard Questions

Order:
1. **Global config directory creation** (if missing) - asked FIRST
2. Config branch name (suggested: `codeagent-{username}`)
3. Existing devcontainer strategy
4. Optional feature selection
5. Editor preference

The wizard also:
- checks `.gitignore`
- prints guidance if `.opencode` is not ignored
- does not edit ignore rules automatically

## Git Storage Model

### Main Model

- `.opencode/` lives inside the target repository
- `.opencode/` is a nested linked Git worktree
- that worktree is used to version per-developer project config separately from the main project history

### Branching Rules

- wizard suggests `codeagent-{username}` as the default branch name
- user chooses the final branch name
- if the branch exists, reuse it
- if the branch does not exist, create it as an orphan branch
- config branch is local by default
- pushing to remote is optional and user-controlled

### Main Branch Cleanliness

- no framework-specific committed traces should be added to the main project branch
- `.opencode/` may be ignored by the user manually, but the framework does not edit ignore config automatically

### Existing .opencode/

If `.opencode/` already exists:
- normal `init` exits with explanation
- `init --force` backs it up and replaces it

The framework does not try to distinguish between framework-managed and unrelated `.opencode/` content in v1.

### Backup Rule

Backup naming convention: `.opencode.backup-<timestamp>`

Backups are created at project root, not inside `.opencode/`.

For worktrees, the directory is copied before removal. For non-worktrees, it is moved.

### Commit Behavior

- the framework never auto-commits generated config
- commit and push decisions stay with the developer

## Runtime Layout

### .opencode/ Root

The `.opencode/` directory is both:
- the project-level `opencode` config root
- the per-developer framework worktree root

### Root-Level Contents

- native `opencode` project config in the layout expected by `opencode`
- `devcontainer.json`
- `.env`
- `README.md`
- `.gitignore`

### Runtime Data

All mutable runtime state lives under `.opencode/runtime_data/`:
- `.cache/` - XDG cache directory
- `.local/share/` - XDG data directory
- `.local/state/` - XDG state directory

These directories are mounted into the devcontainer and persist across container rebuilds.

### Runtime Env File

`.opencode/.env` contains project-level runtime and configuration inputs:
- `OPENCODE_VERSION` — opencode version to use
- provider base URL overrides
- `DEFAULT_MODEL`, `SMALL_MODEL`
- `EDITOR`
- notification command

### Versioned vs Local Data

Versioned in the config worktree:
- project-level config
- generated runtime wiring files
- local usage documentation

Not intended for versioning:
- mutable data under `.opencode/runtime_data/`

## Devcontainer Strategy

### Existing Devcontainer Detection

Only these standard locations are treated as existing devcontainers:
- `.devcontainer/devcontainer.json`
- `.devcontainer.json`
- `.devcontainer/devcontainer.yaml`
- `.devcontainer/devcontainer.yml`

Nonstandard locations are ignored.

### Existing Devcontainer Handling

If a standard devcontainer exists:
- inspect it for compatibility with framework requirements
- if compatible, allow the user to choose extending it
- if incompatible, explain what is incompatible, advise using "from scratch" option, and exit

The framework does not try to patch around incompatible devcontainer setups automatically.

### Generated Devcontainer Role

`.opencode/devcontainer.json` is the canonical generated runtime entrypoint.

V1 aims to express behavior through `devcontainer.json` only. Helper scripts are out of scope.

### Default Features

Always present:
- Git inside container
- common shell utilities

### Optional Features

- DinD / Docker access
- `vi`
- `nano`
- Python + Poetry
- Node.js + npm
- Java + Maven

Feature selection is not stored separately. The generated `devcontainer.json` is the source of truth.

### DinD Rule

DinD is opt-in only.

If selected, setup must:
- check that a rootless Docker context exists
- launch will use `DOCKER_CONTEXT=rootless` by default

Reason: avoid privileged DinD as the default path, keep security tradeoffs explicit.

### Launch Command

After `init`, the framework prints:
- `ocframework launch` - start the container
- `ocframework launch --debug config` - debug configuration
- `docker exec -it <container_name> /bin/bash` - shell access (find container name with `docker ps | grep ocf-`)
- `ocframework launch --docker-context <name>` - override Docker context

The generated devcontainer configuration auto-starts `opencode` via `postAttachCommand`.

## Security Model

### Mount Permissions

Read-only mounts:
- global `opencode` config directory (only if present or created during init)
- framework repository at `OCF_LOCAL_FRAMEWORK_PATH` (required)
- framework-level config directory
- project-level config in `.opencode/`
- auth file: global auth when present, or framework stub auth otherwise

Read-write mounts:
- `.opencode/runtime_data/`
- project source repository

### Host-Side Path Discovery

All host-side paths are discovered in the **local user context**, not the process user context:
- If running under `sudo`, uses `SUDO_USER`'s home directory
- Respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME` from the local environment
- Falls back to `HOME` environment variable
- Only as a last resort uses the process user's home

### Global Auth File

- discovered at `$XDG_DATA_HOME/opencode/auth.json` or `~/.local/share/opencode/auth.json`
- uses local user context for path resolution
- if present on the host, mounted read-only
- if absent, framework stub auth is used from `${OCF_LOCAL_FRAMEWORK_PATH}/framework-nuts-and-bolts/stub-auth.json`

Intent:
- allow the agent to use existing host auth when available
- avoid privilege escalation via injected credentials
- keep the auth file immutable inside the container

### Docker Access Rule

Docker access is not enabled by default.

If Docker access is selected:
- require rootless Docker context handling
- `DOCKER_CONTEXT=rootless` is set by the CLI for devcontainer subprocess only
- keep the security consequence explicit in setup validation

### Config Immutability

The agent must not be able to modify:
- global config
- framework config
- project config

This preserves reviewability and prevents silent mutation of declared configuration layers.

### Scope of Framework Responsibility

The framework does not compute effective agent configuration.

Its security responsibility is to:
- validate prerequisites including framework repository validity
- expose the intended config layers
- apply mount access rules correctly
- keep sensitive paths constrained where policy requires it
- fail fast when framework repository is missing or invalid

## Tech Stack

### Primary Stack

- `Python 3.12+` - implementation language
- `pipx` - installation and distribution
- `git` - repository validation, orphan-branch creation, linked worktree management
- `Docker` - isolation boundary
- `devcontainer-cli` - build and run configured environment
- `opencode` - coding agent engine

### Python Libraries

- `Typer` - CLI commands and interactive setup wizard
- `pydantic` - validation of generation inputs and internal models
- Python standard library: `pathlib`, `subprocess`, `shutil`, `json`, `datetime`

### Generated Artifact Formats

- JSON for `devcontainer.json`
- `.env` for project-level runtime and configuration inputs
- Markdown for generated local usage documentation
- native `opencode` project config layout in `.opencode/`

### Test Stack

- `pytest` - unit and integration-style tests
- fixture repos for Git/worktree scenarios
- subprocess-driven tests for CLI preflight and generation flows

### Intentional Omissions

- no database
- no background service or daemon
- no framework-specific launch service
- no custom config precedence engine

## Directory Structure

### framework-config/

Contains framework-level configuration templates and defaults.

These files are mounted read-only into devcontainers created by the framework, and `OPENCODE_CONFIG` environment variable points to the mount path.

Mount path inside containers: `/opt/ocframework/config`

### framework-nuts-and-bolts/

Storage for reusable pieces of `opencode` configuration that are expected to be symlinked to a project config on demand.

Contains:
- additional agents
- skills
- tools
- other reusable configuration units

The `stub-auth.json` file in this directory is used as fallback auth when no global auth is present on the host.

## Repo-Specific Rules

- `home` directory is excluded from project-related files
- `.idea` directory is excluded from project-related files
- `docker-compose.yaml` is excluded from project-related files
- `.env` is excluded from project-related files
- `.env.sample` is excluded from project-related files
- `sudoers` is excluded from project-related files
- `opencode.dockerfile` is excluded from project-related files
- `/test-project` is a project directory that can be used to test tool application
- package installation via `sudo` is allowed when needed for implementation or testing
