# Tool Adoption Plan: opencode | qwen

Status: **approved design, implementation pending** (branch: `qwen`).
`vision.md`, `AGENTS.md` and this file already describe the target state.

## Goal

Make the agent CLI tool configurable. Both `opencode` and `qwen` (Qwen Code) are
supported through a ToolSpec registry — not a hard replacement. The sandbox part
becomes explicitly tool-agnostic and reusable even without an agent.

## Verified facts: qwen code (v0.22.x)

- Binary `qwen`; npm package `@qwen-code/qwen-code` (requires Node ≥ 22);
  a standalone installer exists (no Node needed) — not used here.
- **No devcontainer feature exists** (checked: GitHub repo/code search, the
  community feature index, and `jsburckhardt/devcontainer-features` which
  provides the opencode feature). Install via generated Dockerfile instead:
  Node 22 (nodesource) + `npm install -g @qwen-code/qwen-code@${OCF_AGENT_VERSION}`.
- Settings scopes, precedence low → high: built-in defaults → system defaults
  (`QWEN_CODE_SYSTEM_DEFAULTS_PATH`) → user (`~/.qwen/settings.json`) →
  project (`.qwen/settings.json`) → system settings
  (`QWEN_CODE_SYSTEM_SETTINGS_PATH`) → environment → CLI args.
- `settings.json` values support `${VAR}` interpolation.
- **No `auth.json`**: API keys via environment (`DASHSCOPE_API_KEY`,
  `OPENAI_API_KEY` + `OPENAI_BASE_URL`); OAuth discontinued upstream.
- Context files: reads `QWEN.md` and `AGENTS.md` natively.
- `qwen serve` (experimental): `--hostname`/`--port` (default 4170), Web Shell
  UI at `/`, `QWEN_SERVER_TOKEN` required for non-loopback binds.
- Mutable state lives under `~/.qwen/` → persists via the existing
  home → `runtime_data/` mount; a read-only single-file mount at
  `~/.qwen/settings.json` does not conflict with it.

## Three parts and their borders

### Part 1 — Sandbox: `opencode_framework/sandbox/`

Tool-agnostic isolation: devcontainer image build, Docker Compose runtime,
mounts, networks, ports, and the env vars of this layer.

- Modules (moved from): `devcontainer.py` + `generators/devcontainer.py`
  (image/devcontainer build), `generators/compose.py`, `runtime.py`,
  `net.py`, `features.py` (compose reconciliation), `devcontainer.py`.
- Templates owned: `docker-compose.template.yaml` skeleton,
  `devcontainer.template.json`, `dockerfile.template`.
- Agent slots rendered but not known: `{{AGENT_FEATURE}}`, `{{AGENT_INSTALL}}`,
  build args, `{{SERVICE_NAME}}`, `{{ENTRYPOINT}}`, `{{AGENT_ENV}}`,
  `{{AGENT_MOUNTS}}`.
- Env: `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`,
  `OCF_REMOTE_FRAMEWORK_CONFIG_PATH`.
- Border rule: sandbox code never imports tool-specific knowledge; the tool
  registry fills the slots.

### Part 2 — Agent integration: `opencode_framework/agent/`

- `registry.py` — `ToolSpec` per tool: binary/compose service name,
  entrypoints, install spec (fills sandbox slots), compose env/mount fragments,
  serve spec (port, token), env-template fragment, global-layer discovery hook,
  version-pin mapping (`OCF_AGENT_VERSION` → feature version / build arg).
- `layers.py` — `.env` tool sections, `.qwen/` project stub generation,
  stub fallbacks, env-var auto-migration.
- Payloads: `framework-config/<tool>/` (framework layer, read-only mount).
- Tool matrix:

| Concern | opencode | qwen |
|---|---|---|
| binary / compose service | `opencode` | `qwen` |
| install | devcontainer feature `jsburckhardt/opencode` | Dockerfile: Node 22 + npm, `OCF_AGENT_VERSION` build arg |
| compose env | `OPENCODE_CONFIG`, `OPENCODE_TUI_CONFIG` | `QWEN_CODE_SYSTEM_DEFAULTS_PATH` |
| framework payload | `framework-config/opencode/{config.json,tui.json,cost-guard.config.json}` | `framework-config/qwen/qwen-settings.json` |
| global layer source | `~/.config/opencode` (dir) + `auth.json` | `~/.qwen/settings.json` (file) |
| project layer | `.opencode/` worktree config | `.qwen/` at project root (generated) |
| auth | `OCF_GLOBAL_AUTH_PATH` (auth.json or stub) | none — API keys via env |
| serve | port 4096, `OPENCODE_SERVER_PASSWORD` optional | port 4170, `QWEN_SERVER_TOKEN` auto-generated |
| context files | `AGENTS.md` | `QWEN.md`, `AGENTS.md` |

### Part 3 — Nuts-and-bolts: `framework-nuts-and-bolts/` (content, no code)

```
framework-nuts-and-bolts/
├── common/      # agents/, commands/, skills/, mcp/idea-example.json
├── opencode/    # plugins/ (+ .gitkeep), tools/, notifier + model-discovery
│                # examples, local-cfg-examples/
└── qwen/        # commands/ (qwen syntax), mcp/ (settings-embedded examples)
```

- Delivery: two per-tool mounts into
  `.opencode/framework-nuts-and-bolts/{common,<tool>}:ro` (replaces the single
  whole-dir mount), emitted by the ToolSpec `{{AGENT_MOUNTS}}` fragment.
- Content migration from current layout: `agents/`, `commands/`, `skills/`,
  `idea-mcp-example.json` → `common/` (`mcp/`); `plugins/`, `tools/`,
  `opencode-notifier-example.json`, `model-autodiscovery.json`,
  `local-cfg-examples/` → `opencode/`; `stub-auth.json` →
  `framework-config/opencode/stubs/`.
- Reference library, not a native discovery path for either tool — contents
  are copied/adapted into the project layer.

## qwen layer wiring (precedence low → high: global < framework < project)

1. **Global**: host `~/.qwen/settings.json` (fallback:
   `framework-config/qwen/stubs/stub-qwen-settings.json` = `{}`) →
   ro file mount → `/opt/ocframework/global/qwen-settings.json` +
   `QWEN_CODE_SYSTEM_DEFAULTS_PATH` pointing there (qwen's *system defaults*
   scope — lowest file scope).
2. **Framework**: `framework-config/qwen/qwen-settings.json` →
   ro file bind → `/home/$REMOTE_USER/.qwen/settings.json` (occupies qwen's
   *user* scope). Content: `model.name: "${OCF_MAIN_MODEL}"`, telemetry off,
   default approval mode, empty `mcpServers`.
3. **Project**: `.qwen/` **generated by ocf at the project root** (stub
   `settings.json`, only-if-missing; `init --force` never overwrites) —
   natively discovered at `/repo/.qwen`; agent-editable; gitignored via the
   same wizard prompt as `.opencode/` (declining = commit as team config).
4. **env**: `.env` merge via compose `--env` (model stack, API keys,
   `QWEN_SERVER_TOKEN`).
5. **CLI args**: launch command.

`QWEN_CODE_SYSTEM_SETTINGS_PATH` is deliberately unused (reserved; using it
would place the framework above project settings).

Serve: `qwen serve --hostname 0.0.0.0 --port 4170` with an auto-generated
`QWEN_SERVER_TOKEN` (`secrets.token_hex(32)`), injected via `--env`, Web Shell
URL + token printed at launch. `qwen serve` is experimental — TUI is the
stable path.

## Environment variable taxonomy

Rule: **variables shared across parts/tools may be unprefixed; part- or
tool-specific ones must be prefixed.**

| Family | Variables |
|---|---|
| shared (no prefix) | `REMOTE_USER`, `XDG_*` |
| sandbox | `OCF_IMAGE_ID`, `OCF_LOCAL_FRAMEWORK_PATH`, `OCF_REMOTE_FRAMEWORK_CONFIG_PATH` |
| agent tool | `OCF_AGENT_TOOL` (`opencode` \| `qwen`), `OCF_AGENT_VERSION` |
| agent layers | `OCF_GLOBAL_CONFIG_PATH` (dir for opencode, file for qwen), `OCF_GLOBAL_AUTH_PATH` (opencode only) |
| agent defaults via env | `OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`, `OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS`, `OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS` |
| tool-native (agent's contract, outside OCF namespace) | `OPENCODE_CONFIG`, `OPENCODE_TUI_CONFIG`, `OPENCODE_SERVER_PASSWORD`, `QWEN_CODE_SYSTEM_DEFAULTS_PATH`, `QWEN_SERVER_TOKEN` |

Renames: `OPENCODE_VERSION` → `OCF_AGENT_VERSION`;
`OCF_LOCAL_GLOBAL_CONFIG_PATH` → `OCF_GLOBAL_CONFIG_PATH`;
`OCF_LOCAL_GLOBAL_AUTH_PATH` → `OCF_GLOBAL_AUTH_PATH`;
`PLAN_MAX_BEFORE_RESPONSE_STEPS` → `OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS`;
`BUILD_MAX_BEFORE_RESPONSE_STEPS` → `OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS`.

## Decision ledger

1. Configurable ToolSpec registry (`opencode` | `qwen`) — not a hard replace.
2. Tool chosen at `init` (wizard prompt + `--tool` flag), persisted as
   `OCF_AGENT_TOOL` in `.opencode/.env`; absent ⇒ `opencode` (backward
   compatible); switching tools = re-init.
3. qwen install via Dockerfile (Node 22 + npm, `OCF_AGENT_VERSION` build arg) —
   no devcontainer feature exists.
4. Layer precedence global < framework < project, wired through qwen's native
   scopes (global = system defaults, framework = user, project = project).
5. Project layer `.qwen/` generated by ocf at the project root,
   only-if-missing; `--force` preserves it.
6. `.qwen/` gitignore mirrors the `.opencode/` wizard prompt.
7. Serve: auto `QWEN_SERVER_TOKEN`, `--env` injection, Web Shell URL printed.
8. Full module restructure: `sandbox/` + `agent/` packages.
9. Env taxonomy as above, with auto-migration of old names.
10. `framework-config/{opencode,qwen}/` full tool subdirs incl. `stubs/`.
11. `framework-nuts-and-bolts/{common,opencode,qwen}/` with per-tool submounts.
12. Global layer for qwen = settings file only (global `QWEN.md` follow-up).

## Changes by file

**New code**
- `opencode_framework/sandbox/` — `devcontainer.py`, `compose.py`,
  `runtime.py`, `net.py`, `features.py` (moved from `generators/` + top level).
- `opencode_framework/agent/registry.py`, `opencode_framework/agent/layers.py`.

**Generators / templates**
- `generators/base.py`: `GenerationContext.agent_tool` (default `opencode`).
- `generators/templates.py`: `{{SERVICE_NAME}}`, `{{ENTRYPOINT}}`,
  `{{AGENT_ENV}}`, `{{AGENT_MOUNTS}}`; env template tool fragment +
  `OCF_AGENT_TOOL=` line.
- `templates/docker-compose.template.yaml`: placeholders per above; two
  nuts-and-bolts submounts replace the whole-dir mount.
- `templates/devcontainer.template.json`: `{{AGENT_FEATURE}}` + qwen
  `build.args.OCF_AGENT_VERSION`.
- `templates/dockerfile.template`: `{{AGENT_INSTALL}}` block.
- `generators/config_files.py`: tool-specific auth vs qwen-global resolution;
  `.qwen/` generation (only-if-missing); gitignore helper covers `.qwen/`.
- `generators/documentation.py` + `templates/readme.template.md`:
  tool-conditional sections incl. the config-layers table.

**CLI**
- `cli/app.py`: `init --tool`; `launch` per-spec service name, serve command,
  container port (4096/4170), token generation/injection; tool-aware wording.

**Config discovery**
- `config.py` / `core/config.py`: `GlobalSettings` gains qwen global settings
  discovery (`~/.qwen/settings.json`).

**Framework repo content**
- `framework-config/opencode/{config.json,tui.json,cost-guard.config.json,stubs/stub-auth.json}`
  (moved); `framework-config/qwen/{qwen-settings.json,stubs/stub-qwen-settings.json}` (new).
- `framework-nuts-and-bolts/` restructure per Part 3 above.
- `preflight.py` `REQUIRED_FRAMEWORK_PATHS` updated to the new layout.

**Tests**
- Parametrize existing generator/compose/CLI/integration tests over both tools.
- New: registry specs, qwen compose/env rendering, launch service command,
  token injection, reconciliation with per-tool entrypoint/mounts, Dockerfile
  `$`-escaping, `.qwen/` only-if-missing + `--force` preserves, env migration
  (old→new keys, user keys preserved, idempotent).

## Migration & backward compatibility

- Auto-migrate `.opencode/.env` during reconciliation: rewrite renamed keys
  (values preserved, user-added keys kept verbatim, idempotent), log one line;
  compose regenerated with new references (`/opt/ocframework/config/opencode/…`
  subpaths, two nuts mounts).
- `OCF_AGENT_TOOL` absent ⇒ opencode; entrypoint and mounts unchanged for
  existing opencode projects.
- Tool switch after init requires re-init (documented).
- Framework repo restructure ⇒ each existing project needs one reconciliation
  pass (automatic via the normal update path).

## Implementation order

1. Module restructure (moves + imports; all tests green).
2. `agent/registry.py` + `agent/layers.py`.
3. Templates + generators (slots and fragments).
4. CLI (`init --tool`, launch, serve token).
5. Framework repo content moves + preflight paths.
6. Env renames + auto-migration.
7. Tests.
8. Docs sync (status update in this file, generated README template).

Verification per stage:

```sh
poetry run ruff check .
poetry run ruff format .
poetry run mypy opencode_framework/
poetry run pytest
```

Smoke test (docker permitting): `ocframework init --tool qwen` in a scratch
clone → inspect `.opencode/` + `.qwen/` → `ocframework launch` /
`ocframework launch --server`.

## Follow-ups (out of scope here)

- Mount host `~/.qwen/QWEN.md` (global instructions) when present.
- Pre-seed qwen folder-trust to skip the first-run interactive prompt.
- Contribute a qwen devcontainer feature upstream (would replace
  npm-in-Dockerfile).
- `qwen serve` stabilization upstream.
