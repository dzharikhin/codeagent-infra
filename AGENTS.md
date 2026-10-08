# Agent Instructions

Technical details and code conventions for the OpenCode Framework.

## Setup & Commands

```sh
poetry install                          # Create .venv and install dependencies
source .venv/bin/activate               # Activate virtual environment
poetry run ocframework                  # Run CLI

poetry run ruff check .                 # Lint
poetry run ruff format .                # Format code
poetry run mypy opencode_framework/     # Type checking
poetry run pytest                       # Run all tests
poetry run pytest --cov=opencode_framework     # Run with coverage
poetry run pytest tests/test_preflight.py -v   # Run single test file
poetry run pytest tests/ -k "git" -v           # Run tests matching pattern
poetry build                            # Build package
```

All four gates must pass before a task is complete: `ruff check .`,
`ruff format .`, `mypy opencode_framework/`, `pytest`. Import order is
enforced by ruff's isort rule (I) — `ruff check --fix` auto-fixes; the
88-char limit makes `ruff format` produce moderate wrapping diffs.

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
│   ├── features.py      # Feature set reconciliation on rebuild
│   └── watchdog.py      # Terminates hung docker client when container stops externally
├── cli/
│   ├── __init__.py
│   └── app.py           # Typer CLI commands (init, launch, reconfigure)
├── exceptions/          # Custom exception hierarchy (FrameworkError family)
├── generators/          # Shared generators/assemblers for the active tool's config dir (ctx, templates, env, docs)
├── config.py            # Global settings, framework validation
├── preflight.py         # Preflight checks (git queries come from git_ops)
├── git_ops.py           # Git repository queries + worktree management (single git implementation)
├── wizard.py            # Interactive setup wizard
└── templates/           # Plain-text templates rendered via {{PLACEHOLDER}} replacement
```

## Code Style

- **Imports**: order enforced by ruff isort (I); `ruff check --fix` auto-fixes.
- **Type annotations**: use `typing` (`List`, `Optional`, `Dict`, `Tuple`);
  always annotate parameters and returns; `Path` for file paths, never
  strings; validation results return `Tuple[bool, List[str]]`.
- **Dataclasses** for structured data; `field(default_factory=...)` for
  mutable defaults.
- **Naming**: functions/variables `snake_case`; classes `PascalCase`;
  constants `UPPER_SNAKE_CASE`; private prefix `_`; test classes
  `Test<Feature>`, methods `test_<behavior>`.
- **Docstrings**: Google style for modules, classes, public functions.
- **Errors**: raise custom exceptions from `opencode_framework.exceptions`
  (every framework exception carries `message`, `remediation`, `context`):

```python
raise ValidationError(
    message="Invalid configuration",
    remediation="Run 'ocframework init' to regenerate config",
    context={"path": str(config_path)},
)
```

  Hierarchy: `FrameworkError` (base) → `ValidationError`,
  `PortAllocationError`; `sandbox/runtime.py` defines a separate `EnvError`.
- **CLI**: Typer commands; failures print via `typer.secho(..., fg=..., err=True)`
  plus a YELLOW remediation line, then `raise typer.Exit(1)`.
- **Subprocess**: `subprocess.run(..., capture_output=True, text=True, timeout=...)`;
  timeouts return a synthetic non-zero `CompletedProcess`, never raise.
- **Generators**: extend `FileGenerator`, implement
  `generate(self, ctx: GenerationContext)`; access `ctx.repo_root`,
  `ctx.config_dir`, `ctx.agent_tool`, `ctx.branch_name`, etc.
- **Tests**: classes per feature; descriptive names
  (`test_fails_outside_git_repo`); `tmp_path` for filesystem operations;
  `monkeypatch` for env vars; `pytest.skip()` when prerequisites are missing.

## Architecture Essentials

### CLI Contract

All commands require a valid framework repository (installed via
`pipx install -e <path>`).

- `ocframework init [--tool opencode|qwen|dsh] [--force]` — initialize a
  harness in a Git repo. Fails unless: framework installed editable from a
  valid clone, cwd is the Git repo root, repo not bare, no staged changes.
- `ocframework launch [--tool <t>] [--acp <postfix>] [--allow-dirty]
  [--docker-context <c>]` — launch the container with the configured agent.
  `--acp` is stdio JSON-RPC mode for editors (postfix appended to the
  container name; existing container of that name removed first). Rebuilds
  the image when the cached reference is missing; `--force` also deletes
  the cache and container. A dirty config worktree (`runtime_data/`
  excluded, fail-open on git errors) is a hard error unless `--allow-dirty`.
- `ocframework reconfigure [--tool <t>] [--same]` — reconcile features/env
  (host mirror paths, `GRADLE_OPTS`), re-render the Dockerfile-generating
  `initializeCommand` from current framework code (migrating legacy keys
  such as `docker-in-docker:2`), rebuild the image, update the cache,
  best-effort remove the existing container; never starts containers.
  Prompts are interactive-TTY only; `--same` forces non-interactive.
- `ocframework --version` — version and configuration status.

Multiple harnesses coexist — one per tool (`.opencode/`, `.qwen/`, `.dsh/`),
each with its own `.env`, container, volumes, image tag. Launch target
precedence: `--tool` > auto-detect (exactly one valid config) > interactive
prompt; multiple valid configs without a TTY or `--tool` is a hard error.
Args after `--` pass through to the agent binary; generated documentation
commands always include `--tool <name>`.

### Build vs Runtime

1. **DevContainer (build)** — `devcontainer.json` defines the image via
   features (Python, Node.js, Java, podman, …); build output is a cached
   Docker image.
2. **Docker Compose (runtime)** — `docker-compose.yaml`: env injection, bind
   mounts, named volumes, user/command.

The split enables host env propagation (DevContainer CLI lacks it), fast
starts without rebuilds, persistent dependency caches via named volumes.

### Three-Part Architecture

1. **Sandbox** (`opencode_framework/sandbox/`) — tool-agnostic isolation.
   Never imports tool knowledge; renders agent slots only
   (`{{AGENT_FEATURE}}`, `{{AGENT_INSTALL}}`, `{{AGENT_ENV}}`,
   `{{AGENT_MOUNTS}}`, `{{SERVICE_NAME}}`/`{{ENTRYPOINT}}`, build args).
2. **Agent integration** (`opencode_framework/agent/`) — `registry.py`
   holds one ToolSpec per tool (opencode, qwen, dsh); `layers.py` wires the
   config layers global < framework < project (+ env, CLI args).
3. **Nuts-and-bolts** (repo content
   `framework-nuts-and-bolts/{common,opencode,qwen,dsh}/`) — snippet
   library; `common/` + the active tool's folder are mounted read-only into
   the config dir.

See [vision.md](vision.md).

### Environment Variable Taxonomy

Rule: variables shared across parts/tools may be unprefixed; part- or
tool-specific ones must be prefixed.

| Family | Variables |
|---|---|
| shared (no prefix) | `REMOTE_USER`, `XDG_*` |
| sandbox | `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`, `OCF_LOCAL_PROJECTS_DIR`, `OCF_LOCAL_REPO_ROOT`, `OCF_REMOTE_FRAMEWORK_CONFIG_PATH`, `OCF_SESSION_SUFFIX`, `OCF_NPMRC_PATH`, `OCF_M2_SETTINGS_PATH`, `OCF_GITCONFIG_PATH`, `OCF_SSH_DIR_PATH` |
| agent tool | `OCF_AGENT_TOOL`, `OCF_AGENT_VERSION` |
| agent layers | `OCF_GLOBAL_CONFIG_PATH` (dir for opencode, file for qwen/dsh), `OCF_GLOBAL_AUTH_PATH` (opencode, dsh) |
| agent defaults via env | `OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`, `OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS`, `OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS` |
| tool-native (agent's own contract, never OCF-prefixed) | `OPENCODE_*`, `QWEN_*`, `DSH_*`, `DEEPSEEK_API_KEY`, `DEEPSEEK_SEARCH_BASE_URL` |
| feature defaults (build-tool's own contract, framework-managed) | `GRADLE_OPTS` (pinned to `-Dorg.gradle.daemon=false` in `.env` when the gradle feature is selected) |

- `REMOTE_USER` is derived, not configured: rootless outer daemon → `root`,
  rootful → `vscode` (docker-feature caps-mode contract). The mode is fully
  encoded in `REMOTE_USER` + the compose security block, which `launch`
  validates against the live daemon — no second knob exists.
- `OCF_LOCAL_REPO_ROOT` is the project's absolute host path; the project
  mounts read-write at that identical path inside the container
  (`working_dir` matches). A directly set value wins over the
  `OCF_LOCAL_PROJECTS_DIR / <repo-name>` derivation; a resolved value that
  is not the actual repo root is a hard launch error. Compose references
  use `${OCF_LOCAL_REPO_ROOT:-${PWD}}`.
- Host mirror paths (`OCF_NPMRC_PATH`, `OCF_M2_SETTINGS_PATH`,
  `OCF_GITCONFIG_PATH`, `OCF_SSH_DIR_PATH`) resolve at generation time
  (`init`) and are surgically refreshed by `reconfigure`
  (`features.reconcile_env_for_features` never regenerates `.env`); compose
  uses `${VAR:-/dev/null}` fallbacks (ssh excepted).
- Renamed keys are not migrated: a `.env` contradicting its config
  directory (e.g. mismatched `OCF_AGENT_TOOL`) is a hard launch error —
  regenerate via `ocframework init --force --tool <tool>`.

### Git Worktree Model

- The config worktree lives in the per-tool native dir (`.opencode/`,
  `.qwen/`, `.dsh/`) — a nested linked Git worktree on a separate branch.
- Branch: `codeagent-{username}-{tool}` (per-tool mark because git refuses
  one branch in two worktrees); reuse if it exists, else create an orphan.
- The framework never auto-commits; `launch` refuses a dirty config
  worktree (registered per `git worktree list`; fail-open on git errors) —
  commit/stash/discard, or pass `--allow-dirty`.

### Per-Tool Naming

- Containers: `ocf_<repo>_<tool>`; ACP launches append `_<postfix>` and
  replace an existing container of that name.
- Managed named volumes: `{kind}-{repo}-{tool}` via `managed_volume_name()`
  in `agent/registry.py`; keys append `${OCF_SESSION_SUFFIX:-}` — ACP
  launches set `OCF_SESSION_SUFFIX=_<postfix>` so every session owns its
  volumes; plain/server launches keep the bare shared names.
- Images: `ocf-<repo>-<tool>:latest` via `devcontainer build --image-name`,
  persisted in `<config_dir>/runtime_data/.image_id`, surfaced as
  `OCF_IMAGE_ID`.

### Security Model

Read-only mounts:
- Framework repository, `framework-config/`,
  `framework-nuts-and-bolts/{common,<tool>}/`.
- Global layer: opencode — global config dir (`~/.config/opencode`) + auth
  file; qwen — `~/.qwen/settings.json`; dsh — `~/.dsh/settings.yaml` +
  `~/.dsh/.credentials.yaml` (global if present, else framework stubs /
  `/dev/null`).
- Host `~/.npmrc` (every tool), `~/.m2/settings.xml` (maven feature),
  `~/.gitconfig` (every tool), `~/.ssh` (ssh feature, only when the host
  directory exists).

Read-write mounts:
- `<config_dir>/runtime_data/`.
- Project source repository (including `.qwen/` for qwen).

qwen and dsh authenticate via the env layer (`DASHSCOPE_API_KEY` /
`OPENAI_API_KEY` + `OPENAI_BASE_URL`; `DEEPSEEK_API_KEY` and friends);
dsh's credentials store must be owner-only (mode 0600) and `DSH_HOME` sits
inside the read-write `runtime_data` home so profiles/sessions persist.

### Docker Feature (podman engine, two modes)

The `docker` optional feature provides a Docker-compatible CLI inside the
sandbox; the engine is podman, mode-selected by the outer Docker daemon at
`init`/`reconfigure` (`detect_daemon_rootless` in `sandbox/runtime.py`
probes `docker info`, honoring `--docker-context`):

| Outer daemon | Mode | Agent (`REMOTE_USER`) | Inner engine | `cap_add` | Graph-root volume target |
|---|---|---|---|---|---|
| rootless | caps mode | `root` | rootful podman | `SYS_ADMIN`, `NET_ADMIN` | `/var/lib/containers` |
| rootful | standard mode | `vscode` | rootless podman | — | `/home/vscode/.local/share/containers` |

Invariant: the container agent uid must map to the host developer uid. On
rootless outer daemons only container root maps to the developer, so the
agent runs as root and the inner engine follows into rootful mode (rootless
podman is structurally broken at userns depth 1 under rootlesskit nesting:
multi-line uid_map needs setuid `newuidmap`, EPERM there). On rootful outer
daemons container `vscode` (uid 1000) maps to the developer and rootless
podman needs no caps. Caps mode is strictly narrower than `privileged:
true` (2 caps vs ~41, no host device tree); both caps stay scoped by the
rootlesskit userns — never host root.

Contracts:

- Detection failure with the docker feature selected is a hard error at
  `init`/`reconfigure` (`docker context ls`, `--docker-context`
  remediation); without the feature it only warns. At `launch` it is
  fail-open (YELLOW warning) so transient daemon blips never block work.
- `launch` validates docker-feature harnesses (marker: the managed
  `docker-<repo>-<tool>` volume mount line) against the live daemon: both
  `REMOTE_USER` and the compose security block must match; a mismatch is a
  hard error — switch the daemon (`docker context use <context>` /
  `--docker-context`) or run `ocframework reconfigure`.
- Standard-mode compose adds
  `security_opt: [apparmor=unconfined, seccomp=unconfined]` and
  `devices: [/dev/fuse:/dev/fuse]`; caps-mode compose adds
  `cap_add: [SYS_ADMIN, NET_ADMIN]`. The reconciler strips both modes'
  managed lines always, so mode flips reconcile cleanly in either
  direction.
- The Dockerfile bakes `/etc/containers/containers.conf` with
  `[containers] cgroups = "disabled"` plus `[engine] cgroup_manager =
  "cgroupfs"`, `events_logger = "file"`: the sandbox mounts /sys/fs/cgroup
  read-only, so cgroup creation must be disabled outright — and `cgroups`
  is a `[containers]`-table key, silently ignored under `[engine]`. The
  storage driver stays auto-detected (driver config lives in storage.conf,
  not containers.conf).
- A `/usr/local/bin/docker` wrapper shadows podman-docker's `/usr/bin/docker`
  (podman's rootful/rootless path is decided by euid) plus the
  `/etc/containers/nodocker` sentinel. Standard mode drops a root agent to
  the pre-existing `vscode` account via `runuser`, unsetting the four XDG
  vars (they pin `/home/${REMOTE_USER}/...`, which would redirect the
  rootless graph root off the pinned volume); the graph-root dir is baked
  vscode-owned for volume copy-up. Caps mode execs podman directly after a
  tolerant `mount -o remount,rw /proc/sys` (read-only /proc/sys breaks
  bridge networking); non-root agents get plain rootless podman.
- `BUILDAH_ISOLATION=chroot` is a container ENV: `docker build` (buildah)
  must not spawn a nested OCI runtime, which fails under the sandbox
  seccomp profile.
- Packages merged into the base apt-packages feature: `podman`,
  `podman-docker`, `podman-compose`, `fuse-overlayfs`, `fuse3`, `uidmap`,
  `slirp4netns`, `passt`, `nftables` — distro-paired apt set from the base
  image's Ubuntu release (26.04 "resolute" ships podman 5.x; validated on
  24.04's podman 4.9 — containers.conf keys are stable across 4→5;
  hello-world smoke test is the acceptance check after a distro jump;
  `nftables` ships the `nft` binary netavark's default firewall backend
  executes — not a hard podman dependency, and without it every
  default-network run fails). Subuid/subgid
  ranges are not written: stock Ubuntu `login.defs` makes `useradd`
  auto-allocate `100000:65536`. `reconfigure` refreshes the managed
  package list whenever the docker feature stays active, so package-level
  fixes propagate without a re-init.
- `docker compose` routes through `podman-compose` (compose v2 would need
  `podman system service`, unavailable without systemd). After a daemon
  mode flip, remove the stale graph volume once
  (`docker volume rm docker-<repo>-<tool>`) on `database graph driver
  mismatch`.
- Legacy `docker-in-docker:2` harnesses: `detect()` reports them as the
  `docker` feature; `reconfigure` strips the key, merges the podman
  packages, re-targets the managed volume and re-renders the initializer.
  `reconfigure` always re-renders the `initializeCommand` from current
  framework code, so image-level fixes propagate without a re-init.
- Standard mode assumes host uid 1000 (container `vscode`); on other uids
  prefer a rootless outer daemon, where container root maps to any host
  uid.

### JVM Build Tools

With the `java` feature, `init`/`reconfigure` prompt for Maven/Gradle:

- Maven → `m2-<repo>-<tool>` volume at `/home/$REMOTE_USER/.m2` + the
  `~/.m2/settings.xml` host mirror (only when that host file exists).
- Gradle → `gradle-<repo>-<tool>` volume at `/home/$REMOTE_USER/.gradle` +
  `GRADLE_OPTS="-Dorg.gradle.daemon=false"` pinned in `.env` (a daemon must
  not outlive the ephemeral container); deselection removes only the managed
  line, custom values survive.
- The `.npmrc` mirror mount is feature- and tool-agnostic: always present,
  `/dev/null` fallback.

### Host Identity Mirrors

- `~/.gitconfig` → `/home/$REMOTE_USER/.gitconfig` for every tool, always
  on (`OCF_GITCONFIG_PATH`, `/dev/null` fallback, refreshed by
  `reconfigure`): propagates commit identity, aliases, `insteadOf`
  rewrites, `safe.directory` entries (valid because the repo mounts at its
  identical host path). Host-only settings are tolerated, not sanitized —
  GPG signing without keys, host credential helpers, absolute `[include]`
  paths fail loudly. Only `~/.gitconfig`, not `~/.config/git/config`.
- The `ssh` feature mirrors `~/.ssh` → `/home/$REMOTE_USER/.ssh:ro` (keys,
  `config`, `known_hosts`); footprint is the `openssh-client` apt package
  (also the detection marker). The mount line is emitted only when the
  feature is on AND the host directory exists — no `/dev/null` fallback (a
  char device at `~/.ssh` breaks ssh); `reconfigure` picks it up after the
  directory appears. Everything under `~/.ssh`, including private keys, is
  readable by the agent (`:ro` prevents modification, not reads). Caveats:
  `known_hosts` cannot grow from inside, no ControlMaster sockets,
  passphrase keys cannot unlock non-interactively, absolute `Include`
  directives break (relative ones work). No SSH agent forwarding
  (`SSH_AUTH_SOCK` deliberately not propagated).
