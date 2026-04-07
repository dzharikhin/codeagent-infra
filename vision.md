# Vision

## Goal

Enable a developer to attach an AI coding agent to an existing project safely and efficiently without polluting the main project history with framework-specific artifacts.

## Scope

The development process with an AI agent differs minimally from normal development. The agent handles routine tasks, but all critical decisions remain with the developer, who stays engaged throughout the process.

The framework does not:
- support parallel task execution (significantly different from normal development)
- support "vibe coding" where the agent works autonomously and returns finished results

## Core Principles

1. **Open source** - no dependency on proprietary solutions
2. **Non-invasive** - the codebase remains clean; attaching an AI agent is like choosing an IDE - different developers can work on the same project using different tools with no traces in the codebase
3. **Secure** - the agent runs in an isolated environment; access to files outside the current project is strictly controlled; no secrets are exposed unless explicitly configured
4. **Transparent** - all configuration layers are visible to the developer
5. **Reproducible** - all configuration levels are version-controlled

## Architecture

The agent environment is built from multiple layers:

### 1. Global User Level

Global settings are discovered automatically at fixed paths:
- `~/.config/opencode` - configuration directory
- `~/.local/share/opencode/auth.json` - authentication file

This level contains elements reused across projects:
- provider blacklists/whitelists
- base provider configuration (URLs, models)

Configuration at this level:
- is optional if the user wants to fully configure each of his projects
- cannot be modified by the agent
- is controlled by the developer outside of project work
- may or may not be version-controlled
- changes affect all configured projects

### 2. Framework Level

This level defines the standard usage pattern for AI coding agents:
- isolation settings (containerization, OS versions, tools)
- environment setup (user, paths, utilities)
- agent selection and version
- agent defaults (plugins, interface, models, permissions, limits)
- customization points for project-specific configuration

Configuration at this level:
- cannot be modified by the agent
- is version-controlled independently of development projects
- changes affect all configured projects

### 3. Project Level

Individual settings for each project:
- environment customization for the specific project
- agent configuration (settings, MCP servers, skills, tools)

Configuration at this level:
- is part of the project thus can be modified by the agent
- is controlled by the developer outside agent sessions
- must be version-controlled within the project

## Usage Concept

### Initial Framework Setup

1. Clone the framework repository locally
2. Install the project setup script via `pipx` so it runs in a proper environment

### Initial Project Setup

1. Navigate to the project where you want to attach an AI agent
2. Run the setup script to prepare the project: version control setup, configuration layers, containers, environments
3. Launch the configured AI agent

### Framework Updates

1. Update the framework repository
2. All configured projects automatically pick up configuration template changes

## Non-Goals for V1

- multiple agent backends
- automatic install of missing required dependencies
- automatic repair of broken environments

## Main Decisions

- Only `opencode` is supported in v1
- Project-local root is `.opencode/`
- `.opencode/` is both the per-developer configuration worktree and the standard project-level `opencode` config root
- Main project branch stays free of framework-specific committed artifacts
- Per-developer project config is versioned on a separate branch, local by default
- Framework only wires config layers; `opencode` computes effective configuration

## Success Criteria

- `init` works in a supported Git repo and produces `.opencode/`
- Generated config is sufficient to launch the container with opencode on board
- `opencode` starts automatically from the generated setup
- Project config can be versioned independently from the main project branch
- Missing prerequisites and incompatible states fail with concrete remediation guidance
