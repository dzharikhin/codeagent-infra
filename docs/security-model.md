# Security Model

## Installation Requirement

The framework MUST be installed as an editable package from a git clone:

```sh
pipx install -e <path-to-framework-git-clone>
```

This is the only supported installation method. The framework repository is a required runtime asset, not just a development convenience. It contains:
- Shared configuration templates
- Stub auth file for environments without host auth
- Agent skill definitions and descriptions
- Framework-level configuration

All framework commands fail immediately if the framework repository is not a valid git clone with all required files.

## Isolation Boundary

The agent runs in a devcontainer-backed Docker environment.

The framework is responsible for mounting the right inputs with the right access mode.

## Mount Permissions

Read-only mounts:
- global `opencode` config directory (only if present or created during init)
- framework repository at `OCF_LOCAL_FRAMEWORK_PATH` (required)
- framework-level config directory
- project-level config in `.opencode/`
- auth file: global auth when present, or framework stub auth otherwise

### Host-Side Path Discovery

All host-side paths are discovered in the **local user context**, not the process user context:

- If running under `sudo`, uses `SUDO_USER`'s home directory
- Respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME` from the local environment
- Falls back to `HOME` environment variable
- Only as a last resort uses the process user's home

This ensures that `ocframework init` run as root creates and mounts directories in the actual user's context (e.g., `/home/jrx/.config/opencode`), not in root's context.

### Global Config Directory

**Decision happens at the start of init**, before any other wizard questions.

- if present at init time, it is mounted read-only
- if absent, the init wizard prompts to create it in the local user's context **immediately** (first question)
- if the user accepts, the directory is created before proceeding with other setup
- if the user declines creation, no mount is added to devcontainer.json
- mount source: local host path (e.g., `/home/jrx/.config/opencode`)
- mount target: container path (`${XDG_CONFIG_HOME}/opencode` in container)

### Global Auth File

- discovered at `$XDG_DATA_HOME/opencode/auth.json` or `~/.local/share/opencode/auth.json`
- uses local user context for path resolution
- if present on the host, mounted read-only
- if absent, framework stub auth is used instead

Read-write mounts:
- `.opencode/runtime_data/`
- project source repository

## Config Immutability

The agent must not be able to modify:
- global config
- framework config
- project config

This preserves reviewability and prevents silent mutation of declared configuration layers.

## Auth Rule

Global auth file:
- discovered at `$XDG_DATA_HOME/opencode/auth.json` or `~/.local/share/opencode/auth.json`
- uses local user context (respects SUDO_USER, HOME)
- if present on the host, mount it read-only so the agent can authenticate against providers
- if absent, mount the framework's stub auth file read-only from `${OCF_LOCAL_FRAMEWORK_PATH}/framework-nuts-and-bolts/stub-auth.json`

Intent:
- allow the agent to use existing host auth when available
- avoid privilege escalation via injected credentials
- keep the auth file immutable inside the container
- framework stub auth is a required asset in the framework git clone, not a packaged fallback
- host auth path is always the local user's path, not root's

## Docker Access Rule

Docker access is not enabled by default.

If Docker access is selected:
- require rootless Docker context handling
- `DOCKER_CONTEXT=rootless` is set by the CLI for devcontainer subprocess only
- keep the security consequence explicit in setup validation

## Scope of Framework Responsibility

The framework does not compute effective agent configuration.

Its security responsibility is to:
- validate prerequisites including framework repository validity
- expose the intended config layers
- apply mount access rules correctly
- keep sensitive paths constrained where policy requires it
- fail fast when framework repository is missing or invalid
