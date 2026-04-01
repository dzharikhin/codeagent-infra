# Security Model

## Isolation Boundary

The agent runs in a devcontainer-backed Docker environment.

The framework is responsible for mounting the right inputs with the right access mode.

## Mount Permissions

Read-only mounts:
- global `opencode` config directory at `~/.config/opencode`
- framework-level config directory
- project-level config in `.opencode/`
- global auth file at `~/.local/share/opencode/auth.json` when present on the host

Global settings are discovered at fixed canonical paths without user prompts.

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

Global auth file at `~/.local/share/opencode/auth.json`:
- discovered at a fixed canonical path
- if present on the host, mount it read-only so the agent can authenticate against providers
- if absent, do not synthesize or expose one

Intent:
- allow the agent to use existing host auth when available
- avoid privilege escalation via injected credentials
- keep the auth file immutable inside the container

## Docker Access Rule

Docker access is not enabled by default.

If Docker access is selected:
- require rootless Docker context handling
- `DOCKER_CONTEXT=rootless` is set by the CLI for devcontainer subprocess only
- keep the security consequence explicit in setup validation

## Scope of Framework Responsibility

The framework does not compute effective agent configuration.

Its security responsibility is to:
- validate prerequisites
- expose the intended config layers
- apply mount access rules correctly
- keep sensitive paths constrained where policy requires it
