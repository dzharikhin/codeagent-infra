# Security Model

## Isolation Boundary

The agent runs in a devcontainer-backed Docker environment.

The framework is responsible for mounting the right inputs with the right access mode.

## Mount Permissions

Read-only mounts:
- global `opencode` config directory
- framework-level config directory
- project-level config in `.opencode/`
- neutralized `~/.local/share/opencode/auth.json`

Read-write mounts:
- `.opencode/runtime_data/`
- project source repository

## Config Immutability

The agent must not be able to modify:
- global config
- framework config
- project config

This preserves reviewability and prevents silent mutation of declared configuration layers.

## Auth Isolation Rule

`~/.local/share/opencode/auth.json` must always be mounted as:
- an empty file
- read-only

Intent:
- keep nearby user state available where needed
- deny useful persisted auth material to the agent through this file

## Docker Access Rule

Docker access is not enabled by default.

If Docker access is selected:
- require rootless Docker context handling
- wire `DOCKER_CONTEXT=rootless`
- keep the security consequence explicit in generated config and setup validation

## Scope of Framework Responsibility

The framework does not compute effective agent configuration.

Its security responsibility is to:
- validate prerequisites
- expose the intended config layers
- apply mount access rules correctly
- keep sensitive paths constrained where policy requires it
