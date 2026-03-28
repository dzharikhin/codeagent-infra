# Vision

## Goal

Enable a developer to attach an AI coding agent to an existing project safely and efficiently without polluting the main project history with framework-specific artifacts.

## V1 Product Slice

V1 optimizes for attaching the framework to an existing Git repository.

Success scenario:
1. A developer enters an existing project repository.
2. They run the framework setup command.
3. The framework validates the environment and repository.
4. The framework creates a dedicated `.opencode` configuration area for this developer.
5. The developer launches the prepared environment with `devcontainer` and gets `opencode` started automatically.

## Core Principles

- open source stack only
- minimal deviation from a normal development workflow
- no framework-specific committed traces in the main project history
- explicit isolation boundaries
- configuration is versioned and reviewable
- framework does not take over developer decisions that should remain explicit

## Non-Goals for V1

- multiple agent backends
- cross-machine portability of per-project developer config
- automatic install of missing dependencies
- automatic repair of broken environments
- framework-owned launch wrapper beyond setup output
- custom configuration merge engine on top of `opencode`

## Main Decisions

- Only `opencode` is supported in v1.
- The project-local root is `.opencode/`.
- `.opencode/` is both:
  - the dedicated per-developer configuration worktree
  - the standard project-level `opencode` config root
- The main project branch stays free of framework-specific committed artifacts.
- Per-developer project config is versioned on a separate branch, local by default and pushable optionally.
- The framework only wires config layers; `opencode` computes effective configuration.

## Config Layers

The framework exposes three layers to `opencode`:
- global user-home `opencode` config, if present
- framework-level custom config
- project-level config from `.opencode/`

The framework does not implement precedence rules between them.

## V1 Success Criteria

- `init` works in a supported Git repo and produces `.opencode/`
- generated config is enough to launch the environment through `devcontainer`
- `opencode` starts automatically from the generated devcontainer setup
- project config can be versioned independently from the main project branch
- missing prerequisites and incompatible states fail with concrete remediation guidance
