# Agent Instructions

Technical details and code conventions for the OpenCode Framework.

**Active plan:** [tool-adoption.md](tool-adoption.md) — configurable agent tool
(`opencode` | `qwen`), 3-part restructure, and env-var taxonomy.
[dsh.md](dsh.md) — adds `dsh` (DeepSeek Harness) as the third supported tool.
The layout and conventions on this page describe the target state of those plans.

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
│   ├── registry.py      # ToolSpec registry (opencode | qwen | dsh)
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

- `ocframework init [--tool opencode|qwen|dsh]` - Initialize framework in a Git repository
- `ocframework launch [--tool opencode|qwen|dsh] [--acp <postfix>]` - Launch container with the configured agent (`--acp <postfix>`: ACP stdio JSON-RPC mode for editors; supported for opencode and qwen. The postfix is required and appended to the container name; any existing container with that name is removed first — reuse a postfix to replace the previous session. A watchdog thread (`sandbox/watchdog.py`) polls the run container once it is observed running and terminates a hung docker client when the container is confirmed stopped/removed externally, so launch exits 137 instead of hanging). When the cached image reference is missing (e.g. pruned by a Docker cleanup), launch rebuilds the image and updates the cache automatically; `launch --force` additionally deletes the cached image ID and removes any existing container
- `ocframework reconfigure [--tool opencode|qwen|dsh]` - Reconfigure an existing harness: feature/port prompts (interactive TTY only — non-TTY runs skip the prompts and keep the detected selection, but still reconcile), refresh the Dockerfile-generating `initializeCommand` from current framework code (migrating legacy feature keys such as `docker-in-docker:2`), reconcile the `.env` feature entries (host mirror paths, `GRADLE_OPTS`), rebuild the image, update the cache, and best-effort remove the tool's existing container; never starts containers
- `ocframework --version` - Print version and configuration status

All commands require a valid framework repository (installed via `pipx install -e <path>`).

Multiple harnesses can coexist in one project — one per tool, each with its own
isolated config directory (`.opencode/`, `.qwen/`, `.dsh/`), `.env`, container,
volumes, and image tag. `init --tool <name>` adds a harness without touching
existing ones. `launch` detects configured harnesses: one valid config launches
directly, several valid configs prompt for a choice (interactive TTY; hard error
with `--tool` remediation when non-interactive).

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
2. **Agent integration** (`opencode_framework/agent/`) — `registry.py` holds one ToolSpec per tool (opencode, qwen, dsh); `layers.py` wires the config layers global < framework < project (+ env, CLI args).
3. **Nuts-and-bolts** (repo content `framework-nuts-and-bolts/{common,opencode,qwen,dsh}/`) — snippet library; `common/` + the active tool's folder are mounted read-only into `.opencode/framework-nuts-and-bolts/`.

### Environment Variable Taxonomy

Rule: variables shared across parts/tools may be unprefixed; part- or tool-specific ones must be prefixed.

| Family | Variables |
|---|---|
| shared (no prefix) | `REMOTE_USER`, `XDG_*` |
| sandbox | `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`, `OCF_LOCAL_PROJECTS_DIR`, `OCF_LOCAL_REPO_ROOT`, `OCF_REMOTE_FRAMEWORK_CONFIG_PATH`, `OCF_SESSION_SUFFIX`, `OCF_NPMRC_PATH`, `OCF_M2_SETTINGS_PATH`, `OCF_GITCONFIG_PATH`, `OCF_SSH_DIR_PATH` |
| agent tool | `OCF_AGENT_TOOL`, `OCF_AGENT_VERSION` |
| agent layers | `OCF_GLOBAL_CONFIG_PATH` (dir for opencode, file for qwen/dsh), `OCF_GLOBAL_AUTH_PATH` (opencode, dsh) |
| agent defaults via env | `OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`, `OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS`, `OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS` |
| tool-native (agent's own contract, never OCF-prefixed) | `OPENCODE_*`, `QWEN_*`, `DSH_*`, `DEEPSEEK_API_KEY`, `DEEPSEEK_SEARCH_BASE_URL` |
| feature defaults (build-tool's own contract, framework-managed) | `GRADLE_OPTS` (pinned to `-Dorg.gradle.daemon=false` in `.env` whenever the gradle feature is selected) |

`REMOTE_USER` is derived, not configured: `init`/`reconfigure` set it from
the outer daemon mode (rootless → `root`, rootful → `vscode` — the
docker-feature caps-mode contract; see the Docker Feature section). No
separate `OCF_PODMAN_CAPS`-style variable exists because the mode is fully
encoded in `REMOTE_USER` plus the compose security block, which `launch`
validates against the live daemon; adding a second knob would only create a
way for the two to disagree.

`OCF_NPMRC_PATH` / `OCF_M2_SETTINGS_PATH` hold the absolute host paths of
`~/.npmrc` and `~/.m2/settings.xml` when those files exist (npmrc for every
tool, settings.xml only when the maven feature is on); empty otherwise.
The compose mirror mounts use `${VAR:-/dev/null}`, so an unset/empty value
is a harmless no-op. `OCF_GITCONFIG_PATH` follows the same npmrc pattern for
`~/.gitconfig` (always on), and `OCF_SSH_DIR_PATH` for the ssh feature's
`~/.ssh` directory mirror — except that the ssh mount line carries no
`/dev/null` fallback (a char device at `~/.ssh` would break ssh), so the
line is emitted only when the feature is on and the host directory exists
at generation time; run `reconfigure` after creating `~/.ssh` to pick it
up. `init` resolves all of them at generation time (host home via
`config.get_local_home`); `reconfigure` re-checks them on every run via
`features.reconcile_env_for_features`, which surgically updates just these
keys and the managed `GRADLE_OPTS` line in `.env` (never regenerating the
file, preserving user edits; on a custom `GRADLE_OPTS` it pins the managed
value when gradle is selected and leaves it alone when deselected).

`OCF_LOCAL_REPO_ROOT` is the project repository's absolute host path; the
project is mounted read-write at that identical path inside the container
(`working_dir` matches). `launch` computes it as
`OCF_LOCAL_PROJECTS_DIR / <repo-name>`: the projects directory comes from the
env layers (global `.env` < project `.env` < override file < CLI `-e`, `~`
expanded) and stays host-side — only `OCF_LOCAL_REPO_ROOT` is exported into
the container. A directly set `OCF_LOCAL_REPO_ROOT` (any env layer) wins
over the derivation and is also `~`-expanded. When `OCF_LOCAL_PROJECTS_DIR`
is unset, launch falls back to the repository's parent directory with a
console note; when the resolved value (direct or derived) is not the actual
repository root, launch is a hard error with source-specific remediation
(fix the env file or override per-launch with
`-e OCF_LOCAL_REPO_ROOT=...` / `-e OCF_LOCAL_PROJECTS_DIR=...`) — this
prevents Docker from silently auto-creating an empty directory at the wrong
path.
Compose references use `${OCF_LOCAL_REPO_ROOT:-${PWD}}`: when the variable is
unset or empty (e.g. running `docker compose -f <config_dir>/docker-compose.yaml`
directly), they fall back to `PWD` — invoke from the repository root for the
fallback to resolve correctly.

Renamed keys are not migrated: a `.env` whose `OCF_AGENT_TOOL` is missing or
contradicts its config directory (`.opencode/` = opencode, `.qwen/` = qwen,
`.dsh/` = dsh) is a hard launch error with a re-init remediation — regenerate
via `ocframework init --force --tool <tool>` (existing directory backed up
first). The same applies to harnesses generated before `OCF_LOCAL_REPO_ROOT`
existed: their compose files still mount the project at `/<repo>` (only the
python venv mount line is migrated by a feature rebuild); re-run
`ocframework init --force --tool <tool>` to get host-path mounting. Harnesses
from before the `OCF_LOCAL_PROJECTS_DIR` split baked the full repo path into
`.env`: correct while the repository stays put (the direct value is honored),
but a hard launch error after moving it — re-init to regenerate.

### Git Worktree Model

- The config worktree lives in a per-tool native dir: `.opencode/`
  (opencode), `.qwen/` (qwen) or `.dsh/` (dsh) — a nested linked Git
  worktree on a separate branch
- Branch name suggested: `codeagent-{username}-{tool}` for every tool
  (e.g. `codeagent-alice-opencode`, `codeagent-alice-qwen`,
  `codeagent-alice-dsh`); git refuses to check out one branch in two
  worktrees, hence the per-tool mark
- If branch exists, reuse it; otherwise create orphan branch
- Framework never auto-commits; developer controls commits

### Per-Tool Naming

- Containers: `ocf_<repo>_<tool>` (e.g. `ocf_myrepo_dsh`); ACP launches
  append a required postfix — `ocf_<repo>_<tool>_<postfix>` (e.g.
  `ocf_myrepo_opencode_zed`) — and remove an existing container of the same
  name first, so concurrent ACP sessions never collide and a reused postfix
  replaces the previous session
- Managed named volumes: `{kind}-{repo}-{tool}` (e.g. `venv-myrepo-qwen`,
  `m2-myrepo-qwen`, `gradle-myrepo-qwen`, `docker-myrepo-qwen`) via
  `managed_volume_name(prefix, repo_name, tool)` in `agent/registry.py` —
  two agents can run concurrently on one repo without sharing mutable state.
  Managed volume keys carry a `name:` attribute appending
  `${OCF_SESSION_SUFFIX:-}` (`managed_volume_keys`): ACP launches set
  `OCF_SESSION_SUFFIX=_<postfix>` (e.g. `docker-myrepo-opencode_zed`), so
  every session owns its volumes — concurrent sessions must never share
  mutable volumes such as the podman graph root; plain/server launches leave
  the suffix empty and keep the bare shared names. Stale per-postfix volumes
  accumulate and are removed manually (`docker volume rm`). Compose files
  generated before this change keep shared volumes until re-init
  (`ocframework init --force --tool <tool>`)
- Built images: `ocf-<repo>-<tool>:latest` (e.g. `ocf-myrepo-dsh:latest`),
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
- Global layer, per tool: opencode — global config directory (host: `~/.config/opencode`) + auth file (global auth if present, else framework stub); qwen — `~/.qwen/settings.json` (global if present, else framework stub); dsh — `~/.dsh/settings.yaml` (global if present, else `/dev/null`) + `~/.dsh/.credentials.yaml` (global if present, else framework stub)
- qwen framework settings at `/home/$REMOTE_USER/.qwen/settings.json`
- Host `~/.npmrc` at `/home/$REMOTE_USER/.npmrc` for every tool, and host
  `~/.m2/settings.xml` at `/home/$REMOTE_USER/.m2/settings.xml` when the
  maven feature is on — only when those files exist (`OCF_NPMRC_PATH` /
  `OCF_M2_SETTINGS_PATH` empty mounts `/dev/null` instead; the settings.xml
  bind sits on top of the `m2-*` named volume, which wins by mount depth)
- Host `~/.gitconfig` at `/home/$REMOTE_USER/.gitconfig` for every tool,
  always on (`OCF_GITCONFIG_PATH` empty mounts `/dev/null` instead) — see
  the Host Identity Mirrors section
- Host `~/.ssh` directory at `/home/$REMOTE_USER/.ssh:ro` when the ssh
  feature is on and the directory exists (see the Host Identity Mirrors
  section for the trust posture and caveats)

Read-write mounts:
- `<config_dir>/runtime_data/` (`.opencode/runtime_data/`, `.qwen/runtime_data/` or `.dsh/runtime_data/`)
- Project source repository (including `.qwen/` for qwen)

qwen has no auth file: API keys (`DASHSCOPE_API_KEY`, `OPENAI_API_KEY` + `OPENAI_BASE_URL`) are injected via the env layer.

dsh is env-based too: `DEEPSEEK_API_KEY` (and friends) come from the env layer
(`.dsh/.env`, host `~/.dsh/.env`, or `launch -e`); the host `.credentials.yaml`
store is mounted read-only and must be owner-only (mode 0600 — dsh refuses to
boot otherwise; `init` chmods the framework stub, re-run `init --force --tool
dsh` after a fresh framework clone). `DSH_HOME` is pinned to
`/home/$REMOTE_USER/.dsh`, i.e. inside the read-write `runtime_data` home, so
profiles/sessions persist. Web UI saves to settings/credentials fail against
the read-only mounts by design — edit on the host (settings hot-reload).

The docker feature's elevated surface is mode-scoped (see the Docker Feature
section): standard mode grants no capabilities at all; caps mode grants
exactly `SYS_ADMIN` + `NET_ADMIN`. For comparison, `privileged: true` grants
all ~41 capabilities plus the full host device tree and module loading —
caps mode is strictly narrower, and both caps remain confined by the outer
rootlesskit user namespace: they apply to container root, which on a rootless
daemon maps to the unprivileged host developer, never to host root.

### Docker Feature (podman engine, two modes)

The `docker` optional feature (wizard key `docker`) provides a Docker-compatible
CLI inside the sandbox; the engine is podman, in one of two modes selected by
the outer Docker daemon at `init`/`reconfigure` time
(`detect_daemon_rootless` in `sandbox/runtime.py` probes
`docker info --format '{{json .SecurityOptions}}'`, honoring
`--docker-context`):

| Outer daemon | Mode | Agent (`REMOTE_USER`) | Inner engine | `cap_add` | Graph-root volume target |
|---|---|---|---|---|---|
| rootless | caps mode | `root` | rootful podman | `SYS_ADMIN`, `NET_ADMIN` | `/var/lib/containers` |
| rootful | standard mode | `vscode` | rootless podman | — | `/home/vscode/.local/share/containers` |

The invariant driving the split: the container agent uid must map to the host
developer uid. On rootless outer daemons only container root maps to the host
developer, so the agent must run as root — and the inner engine follows it
into rootful mode (rootless podman is structurally broken at userns depth 1
under rootlesskit nesting: the multi-line uid_map needs setuid `newuidmap`,
which is EPERM there). On rootful outer daemons container `vscode` (uid 1000)
maps to the host developer and rootless podman needs no capabilities.

Caps mode is strictly narrower than `privileged: true` (2 caps vs 41, no host
device tree, no module loading); both caps stay scoped by the rootlesskit
userns — never host root. Probe-derived support: CapEff
`0xa80425fb → 0xa82435fb`; `CAP_SYS_ADMIN` lets crun mount /proc at userns
depth 1 (depth-2 fresh unshare is kernel-denied), `CAP_NET_ADMIN` sets up
bridge networking — the remaining blocker was the read-only /proc/sys
inherited from the outer rootless daemon's proc mount, fixed by a tolerant
`mount -o remount,rw /proc/sys` in the wrapper's root branch.

Detection and enforcement contract:

- `init`/`reconfigure` detect the daemon mode after feature selection and
  print e.g. `Docker daemon: rootless → caps mode (SYS_ADMIN, NET_ADMIN),
  REMOTE_USER=root`; `REMOTE_USER` is derived (rootless → `root`, rootful →
  `vscode`) and surgically written to `.env` after generation (init) /
  unconditionally enforced (reconfigure).
- A detection failure with the docker feature selected is a hard error at
  `init`/`reconfigure` (a harness cannot be generated against an unknown
  daemon; remediation: check `docker context ls`, pass `--docker-context`).
  Without the docker feature it only warns and keeps the `REMOTE_USER=root`
  template default. At `launch` it is fail-open (YELLOW warning, validation
  skipped) so transient daemon blips never block work.
- `launch` validates docker-feature harnesses (marker: the managed
  `docker-<repo>-<tool>` volume mount line) against the live daemon mode —
  both the harness's `REMOTE_USER` and its compose security block must
  match. A mismatch is a hard error naming both sides, with two remediations:
  point launch at a matching daemon (`docker context use <context>` or
  `ocframework launch --docker-context <context>`) or regenerate the harness
  for this daemon with `ocframework reconfigure`.

Packages merged into the base `apt-packages` feature: `podman`,
`podman-docker` (Docker CLI shim), `podman-compose`, `fuse-overlayfs`,
`fuse3`, `uidmap`, `slirp4netns`, `passt` — the distro-paired set from Ubuntu
24.04 (podman 4.9 + podman-compose 1.0.6), all from apt with no pip steps.

Standard mode (rootful outer daemon):

- The generated `docker-compose.yaml` adds `security_opt:
  [apparmor=unconfined, seccomp=unconfined]` (rootless podman's crun requires
  syscalls absent from Docker's default seccomp profile) and `devices:
  [/dev/fuse:/dev/fuse]` for fuse-overlayfs. No `privileged: true`, no
  `cap_add`.
- The Dockerfile bakes a minimal `/etc/containers/containers.conf`
  (`[containers] cgroups = "disabled"` plus `[engine] cgroup_manager =
  "cgroupfs"`, `events_logger = "file"`): the sandbox mounts /sys/fs/cgroup
  read-only, so cgroup creation must be disabled outright — the cgroupfs
  fallback alone still tries to create `/libpod_parent` and crun dies with
  `cgroup.subtree_control: Read-only file system` (validated manually:
  `docker run hello-world` fails without the key, works with
  `--cgroups=disabled`). `cgroups` is a `[containers]`-table key — placed
  under `[engine]`, podman never applies it. The storage driver stays
  auto-detected (overlay / fuse-overlayfs).
- The Dockerfile bakes the `/etc/containers/nodocker` sentinel (silences the
  "Emulate Docker CLI" shim notice) and a `/usr/local/bin/docker` wrapper
  shadowing podman-docker's `/usr/bin/docker`: podman has no "run as another
  user" override (its rootful/rootless path is decided by euid), so a root
  agent is dropped to the pre-existing `vscode` service account via
  `runuser`, with the four XDG base-directory vars unset in between (the
  agent env pins them to `/home/${REMOTE_USER}/...`, which would redirect the
  rootless graph root away from the pinned volume; unset, podman falls back
  to HOME-based defaults under `/home/vscode`). Non-root agents exec podman
  directly. Subuid/subgid ranges are not written: stock Ubuntu 24.04
  `login.defs` (`SUB_UID_MIN=100000`, `SUB_UID_COUNT=65536`) makes `useradd`
  auto-allocate `100000:65536` at user creation, which rootless podman picks
  up; base images deviating from that would need the entries added back.
- The graph-root volume target is pinned at `/home/vscode/.local/share/containers`
  (independent of `REMOTE_USER`, because the wrapper always runs podman with
  `HOME=/home/vscode`); the directory is baked vscode-owned into the image so
  a fresh named volume's copy-up inherits that ownership (an empty root-owned
  volume would leave rootless podman unable to write its graph root).

Caps mode (rootless outer daemon):

- The compose security block is the standard block plus
  `cap_add: [SYS_ADMIN, NET_ADMIN]`; the graph-root volume target is
  `/var/lib/containers` (rootful podman's default — root writes it freely, no
  ownership bake).
- The Dockerfile bakes `/etc/containers/containers.conf` with the rootful
  fallbacks (cgroupfs manager, file events logger — none auto-detectable
  without systemd/journald) and `[containers] cgroups = "disabled"` (the
  sandbox's read-only /sys/fs/cgroup, as in standard mode; the key must sit
  in the `[containers]` table — under `[engine]` podman silently ignores it
  and every `docker run` fails with `crun: ... cgroup.subtree_control:
  Read-only file system`, observed in the manual hello-world validation).
  The storage driver stays auto-detected and lands on overlay — `[storage]`
  is not a containers.conf table (driver config lives in storage.conf), so
  an earlier vfs pin sat silently ignored while rootful podman mounted
  overlay anyway (docker info inside the sandbox showed `graphDriverName:
  overlay` with the pin present); the pin is dropped. Also baked: the
  nodocker sentinel and a wrapper whose root branch execs podman directly
  after the tolerant /proc/sys remount (no `runuser`, no vscode delegation,
  no XDG unsetting); non-root agents get plain rootless podman as a defensive
  fallback.

Both modes:

- `BUILDAH_ISOLATION=chroot` is set as a container ENV so `docker build` (→
  buildah) uses chroot isolation inside the already-isolated sandbox (the
  default `oci` isolation spawns a nested OCI runtime that fails under the
  sandbox's seccomp profile).
- `docker compose` routes through apt-installed `podman-compose` 1.0.6
  (auto-detected on PATH; it shells out to the podman CLI — compose v2 would
  require `podman system service`, unavailable without systemd). Note 1.0.6
  limitations: no `--wait`, no `COMPOSE_PROFILES`, no healthcheck-condition
  `depends_on` gating.
- The compose reconciler strips both modes' managed lines always, so a mode
  flip reconciles cleanly in either direction (`ocframework reconfigure`
  after switching daemon contexts).
- Mode-flip caveat: after the outer daemon migrates, the persisted graph DB
  was written by the other mode's driver — podman fails with
  `database graph driver mismatch`. Remove the stale volume once
  (`docker volume rm docker-<repo>-<tool>`) and relaunch.
- Legacy `docker-in-docker:2` harnesses are detected and migrated to the
  `docker` feature by `detect()` and the reconciler (the managed
  `docker-<repo>-<tool>` volume is re-targeted from `/var/lib/docker` to the
  podman graph root); `reconfigure` also strips the legacy feature key,
  merges the podman apt packages, and re-renders the Dockerfile
  initializer, so the rebuilt image carries the podman engine. Re-init
  (`ocframework init --force --tool <tool>`) remains the way to a fully
  modernized harness.
- `reconfigure` never freezes build-time state: the Dockerfile-generating
  `initializeCommand` in `devcontainer.json` is re-rendered from current
  framework code on every run, so image-level fixes propagate without a
  re-init; `devcontainer.json` is rewritten whenever its serialized content
  differs (feature changes, legacy migration, initializer drift).

Limitation: standard mode (rootful outer daemon) assumes the host developer's
uid is 1000 (it maps to container `vscode`); on hosts with a different uid
the standard-mode bind-mount ownership match breaks — prefer a rootless outer
daemon there, where container root maps to any host uid.

### JVM Build Tools Support

When the `java` feature is selected, `init`/`reconfigure` prompt for Maven
and/or Gradle:

- Maven adds the `m2-<repo>-<tool>` named volume at `/home/$REMOTE_USER/.m2` plus the `~/.m2/settings.xml` host mirror (only when that host file exists)
- Gradle adds the `gradle-<repo>-<tool>` named volume at `/home/$REMOTE_USER/.gradle` and pins `GRADLE_OPTS="-Dorg.gradle.daemon=false"` in `.env` (a daemon must not outlive the ephemeral container); deselection removes only the managed line, custom values survive
- The `.npmrc` mirror mount is feature- and tool-agnostic: always present, `/dev/null` fallback

### Host Identity Mirrors (git config, SSH)

The host `~/.gitconfig` is mirrored read-only at
`/home/$REMOTE_USER/.gitconfig` for every tool, always on (npmrc pattern:
`OCF_GITCONFIG_PATH` in `.env`, `/dev/null` fallback, refreshed by
`reconfigure`; harnesses generated before the mirror existed gain the mount
on any feature rebuild). This propagates the commit identity
(`user.name`/`user.email`), aliases, `insteadOf` URL rewrites and
`safe.directory` entries — the latter stay valid because the project repo
mounts at its identical host path. Host-only settings that cannot work
inside the sandbox are tolerated, not sanitized (documented failure modes):
`commit.gpgsign`/`signingkey` without GPG keys make commits fail loudly,
credential helpers referencing host binaries (e.g. `!gh auth git-credential`)
are absent, and absolute-path `[include]` directives break. The XDG location
`~/.config/git/config` is not mirrored (scope is `~/.gitconfig` only).

The `ssh` optional feature (wizard key `ssh`) mirrors the host `~/.ssh`
directory read-only at `/home/$REMOTE_USER/.ssh` (keys, `config`,
`known_hosts`), enabling git push/pull over SSH remotes from inside the
sandbox. Its devcontainer footprint is the `openssh-client` apt package
merged into the base apt-packages feature (docker/podman pattern), which
both guarantees the binary and serves as the detection marker. The compose
mount line is emitted only when the feature is on and the host `~/.ssh`
exists at generation time — there is no `/dev/null` fallback because a char
device at `~/.ssh` breaks ssh; `init`/`reconfigure` warn and omit the mount
when the directory is missing, and a later `reconfigure` picks it up. Trust
posture: everything under `~/.ssh` — including private key material — is
readable by the agent inside the container (the uid-mapping invariant makes
the host ownership match); `:ro` prevents modification, not reads. Caveats:
`known_hosts` cannot grow from inside (new host keys must be pre-trusted on
the host), `ControlMaster` sockets cannot be created (ssh degrades to
unmultiplexed connections), passphrase-protected keys cannot be unlocked
non-interactively, and absolute-path `Include` directives in `~/.ssh/config`
break unless the included files live inside `~/.ssh` itself (relative
includes work). No SSH agent forwarding is performed (`SSH_AUTH_SOCK` is
deliberately not propagated).
