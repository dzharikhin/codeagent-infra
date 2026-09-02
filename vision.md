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

The framework consists of three parts with explicit borders. Borders are expressed as module names in code, variable prefixes in `.env`, and directory structure for content.

### Part 1: Sandbox

Tool-agnostic isolation around the project: devcontainer image build, Docker Compose runtime, mounts, networks, ports, and the environment variables belonging to this layer. Barely linked to the agent tool — valuable on its own, it creates a restricted, easily reusable sandbox around a project, better than plain devcontainers.

- Code: `opencode_framework/sandbox/`
- Env: `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`, `OCF_REMOTE_FRAMEWORK_CONFIG_PATH`; shared unprefixed: `REMOTE_USER`, `XDG_*`
- Border rule: sandbox code never imports tool-specific knowledge. Tool installation details arrive only as slot values (`{{AGENT_FEATURE}}`, `{{AGENT_INSTALL}}`, build args, service/entrypoint names, `{{AGENT_ENV}}`, `{{AGENT_MOUNTS}}`) provided by Part 2. Not every tool has a devcontainer feature — installation may fall back to Dockerfile-based install; this remains a sandbox concern fed with tool-specific knowledge.

### Part 2: Agent Tool Integration

Integration of one agent tool (opencode or qwen) and its layered configuration. This part absorbs the tool's configuration complexity:

effective config = global < framework < project (optional) < env < CLI args

- Code: `opencode_framework/agent/` — `registry.py` (one ToolSpec per tool: binary, install, env/mount fragments, serve, version pin), `layers.py` (env sections, project stubs, stub fallbacks, migrations)
- Payloads: `framework-config/<tool>/` — the framework layer, mounted read-only
- Env: `OCF_AGENT_*` (tool selection and version), `OCF_GLOBAL_*` (global layer source), agent defaults as env (`OCF_MAIN/BUILD/SMALL_MODEL`, `OCF_PLAN_/OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS`). Tool-native variables (`OPENCODE_*`, `QWEN_*`) are the agent's own contract — used unprefixed, only for the active tool.

#### Layer 1: Global User Level

Global settings are discovered automatically at fixed per-tool paths:
- opencode: `~/.config/opencode` (configuration directory), `~/.local/share/opencode/auth.json` (authentication)
- qwen: `~/.qwen/settings.json`

This level contains elements reused across projects:
- provider blacklists/whitelists
- base provider configuration (URLs, models)

Configuration at this level:
- is optional if the user wants to fully configure each of his projects
- cannot be modified by the agent (mounted read-only)
- is controlled by the developer outside of project work
- may or may not be version-controlled
- changes affect all configured projects

#### Layer 2: Framework Level

This level defines the standard usage pattern for AI coding agents:
- isolation settings (containerization, OS versions, tools)
- environment setup (user, paths, utilities)
- agent selection and version
- agent defaults (plugins, interface, models, permissions, limits)
- customization points for project-specific configuration

Configuration at this level:
- cannot be modified by the agent (mounted read-only)
- is version-controlled independently of development projects
- changes affect all configured projects

#### Layer 3: Project Level (optional)

Individual settings for each project:
- environment customization for the specific project
- agent configuration (settings, MCP servers, skills, tools)

Configuration at this level:
- is part of the project thus can be modified by the agent
- is controlled by the developer outside agent sessions
- is version-controlled within the project: on the per-developer agent branch (opencode) or, for tool-native project paths (`.qwen/`), deliberately committed as team config (gitignored by default otherwise)
- the framework generates the initial project layer only if missing; existing content is never overwritten

### Part 3: Nuts-and-bolts

A snippet library showing how to configure a tool properly. Split into:
- common - tool-agnostic concepts: agents, commands, skills, MCP examples
- tool-specific - how to make something work in the specific tool

Content lives at `framework-nuts-and-bolts/{common,opencode,qwen}/`. Delivery is tool-conditional: `common/` plus the active tool's folder are mounted read-only into `.opencode/framework-nuts-and-bolts/`. The library is a reference, not a native discovery path — contents are copied or adapted into the project layer.

## Usage Concept

### Initial Framework Setup

1. Clone the framework repository locally
2. Install the project setup script via `pipx` so it runs in a proper environment

### Initial Project Setup

1. Navigate to the project where you want to attach an AI agent
2. Run the setup script to prepare the project: agent tool selection, version control setup, configuration layers, containers, environments
3. Launch the configured AI agent

### Framework Updates

1. Update the framework repository
2. All configured projects automatically pick up configuration template changes

## Non-Goals for V1

- multiple agent tools in one project (exactly one active tool, chosen at init)
- automatic install of missing required dependencies
- automatic repair of broken environments

## Main Decisions

- The agent tool is configurable via a ToolSpec registry (opencode, qwen); one tool per project, chosen at `init`, persisted as `OCF_AGENT_TOOL`; switching tools requires re-init
- The sandbox (Part 1) is tool-agnostic and usable without an agent
- Config precedence: global < framework < project < env < CLI args; the framework only wires configuration layers, the agent tool computes the effective configuration
- Project-local root is `.opencode/`
- `.opencode/` is both the per-developer configuration worktree and the standard framework entry point; project-level agent config lands in the worktree (opencode) or the tool-native project path (`.qwen/`, gitignored by default or committed as team config)
- Main project branch stays free of framework-specific committed artifacts
- Per-developer project config is versioned on a separate branch, local by default
- Framework never auto-commits; developer controls commits

## Success Criteria

- `init` works in a supported Git repo for both tools (`--tool opencode|qwen`) and produces `.opencode/` (plus `.qwen/` for qwen)
- Generated config is sufficient to launch the container with the selected agent on board
- The agent starts automatically from the generated setup
- Project config can be versioned independently from the main project branch, or deliberately committed as team-shared config
- Missing prerequisites and incompatible states fail with concrete remediation guidance
- Existing opencode projects keep working unchanged after the framework update
