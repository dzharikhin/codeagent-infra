# Plan: Add `dsh` (DeepSeek Harness) as a third supported tool

Implementation brief. Execute top to bottom; the "Verification" section is the
definition of done. Reference clone of the tool's source was kept at
`/tmp/opencode/dsh-src` during research (may be gone; facts below are verified).

Repo: https://github.com/deepseek-ai/deepseek-harness — npm package
`@deepseek-ai/dsh`, binary `dsh`, docs site
https://deepseek-harness.github.io/deepseek-harness/.

## Verified dsh facts

- Binary `dsh`; needs Node `^22.19.0 || >=24.0.0` (nodesource `node_22.x`
  already satisfies). Install: `npm install -g @deepseek-ai/dsh@<version>`.
- Harness home: `$DSH_HOME` env var, default `~/.dsh` (see
  `packages/util/home-paths/src/index.ts`). Contains `settings.yaml`,
  `.credentials.yaml`, `.env`, `cordis.patch.yml`, `profiles/`, `sessions/`.
  Profiles auto-initialize on first use → DSH_HOME must be **writable** at
  runtime.
- Credential resolution (see `packages/credentials/credentials-local`):
  inherited process env (wins — "a container `-e` is this run's explicit
  intent") > `$DSH_HOME/.credentials.yaml` > `<cwd>/.env` > `$DSH_HOME/.env`.
  LLM providers take `apiKeyEnv:` credential refs in `settings.yaml`; the
  DeepSeek adapter's default env var is `DEEPSEEK_API_KEY`. `settings.yaml`
  is hot-reloaded.
- **No shipped TUI.** Bare `dsh` exits with `error: --profile <name> is
  required` (`apps/cli/src/args.ts`). The only shipped interactive surface is
  `dsh web` (alias of `--profile web`): HTTP UI on port **3080**, binds
  `127.0.0.1` by default, prints a one-time `?token=<43 chars>` URL, exchanges
  it for a cookie (browser-trust fence accepts IP-literal Host on any port).
- CLI refuses `--host 0.0.0.0` (`packages/bundle/web-app/src/startup.ts`), but
  the `@deepseek-ai/dsh-host-webserver` **config row** natively supports
  `host: 0.0.0.0` ("deliberate network exposure"; README of
  `packages/host/webserver`). The supported workaround is a cordis patch-list
  overlay passed via `dsh web --patch <file>` (the `web` subcommand accepts
  `--patch`).
- Workspace instruction files loaded by base-backed profiles: `AGENTS.md` and
  `CLAUDE.md`.
- Useful native env vars: `DSH_HOME`, `DSH_PERMISSION_MODE`, `DSH_TOOLS_MODE`,
  `DSH_TELEMETRY_MODE` / `DSH_TELEMETRY_DISABLED`, `DEEPSEEK_API_KEY`,
  `DEEPSEEK_SEARCH_BASE_URL`.

## Product decisions (confirmed with the user — do not revisit)

1. **Tool name: `dsh`** → config dir `.dsh/`, branch `codeagent-<user>-dsh`,
   container `ocf_<repo>_dsh`, image `ocf-<repo>-dsh:latest`, volumes
   `<kind>-<repo>-dsh`.
2. **Credentials: env-based model config + RO auth mount.** API keys come from
   the env layer (`DEEPSEEK_API_KEY` via project `.dsh/.env`, host
   `~/.dsh/.env` — the framework already merges that as lowest-priority launch
   env — or `launch -e`). Additionally, host `~/.dsh/.credentials.yaml` (dsh's
   Models-page credential store) is mounted read-only, with an empty framework
   stub fallback — same security shape as the opencode `auth.json` mount.
   `~/.dsh/settings.yaml` is mounted RO when present, `/dev/null` otherwise.
   Consequence (by design): saving keys/settings through the in-container Web
   UI fails; edit on host instead (hot-reload picks it up). The generated
   README must say so.
3. **Plain `launch --tool dsh` keeps running bare `dsh`** (prints the
   `--profile is required` error and exits); `launch --server` is the
   documented dsh flow. **No compose template / `command:` change.**
   A future TUI plugin (e.g. `github.com/gxinxing/deepseek-harness-tui`,
   installed via `dsh plugin`) can later make plain launch interactive —
   out of scope here.

## Changes

### 1. `opencode_framework/agent/registry.py`

- `ToolSpec`: append one defaulted field (after `context_files`, so existing
  specs are untouched):
  `auth_base: Literal["data_home", "home"] = "data_home"`.
- `ServeSpec` docstring: note that `token_env=""` means the tool manages its
  own auth surface (dsh prints a per-boot URL token).
- New constants:
  - `_DSH_CONFIG_DIRNAME = ".dsh"`
  - `_DSH_DOCKERFILE_INSTALL` — clone `_QWEN_DOCKERFILE_INSTALL`
    (nodesource Node 22 + gnupg/apt cleanup) but `npm install -g
    @deepseek-ai/dsh@${OCF_AGENT_VERSION}` and the `# dsh (DeepSeek Harness)`
    comment header.
  - `_DSH_GLOBAL_SETTINGS_MOUNT = "${OCF_GLOBAL_CONFIG_PATH:-/dev/null}:/home/${REMOTE_USER}/.dsh/settings.yaml"`
  - `_DSH_AUTH_MOUNT = "${OCF_GLOBAL_AUTH_PATH:-/dev/null}:/home/${REMOTE_USER}/.dsh/.credentials.yaml"`
- `DSH_TOOL_SPEC = ToolSpec(...)`:
  - `name="dsh"`, `binary="dsh"`, `config_dirname=_DSH_CONFIG_DIRNAME`
  - `serve=ServeSpec(port=3080, token_env="", token_required=False,
    serve_args=("web", "--no-open", "--port", "3080", "--patch",
    "/opt/ocframework/config/dsh/web-bind-all.patch.yml"))`
    (path = `framework-config` RO mount at `OCF_REMOTE_FRAMEWORK_CONFIG_PATH`).
  - `install=InstallSpec(devcontainer_feature=None, feature_version_env=None,
    dockerfile_snippet=_DSH_DOCKERFILE_INSTALL, build_args=("OCF_AGENT_VERSION",))`
  - `compose_env_fragment=_env_line("DSH_HOME", "/home/${REMOTE_USER}/.dsh")` —
    pins the harness home inside the RW, persisted `runtime_data`-backed
    container home. Required: Node `os.homedir()` would otherwise use the
    image's `HOME` (e.g. `/root` for `REMOTE_USER=root`) and miss the mounts.
  - `compose_mount_fragment`: `_mount(_DSH_GLOBAL_SETTINGS_MOUNT)`,
    `_mount(_DSH_AUTH_MOUNT)`, `_nuts_mount("common", ".dsh")`,
    `_nuts_mount("dsh", ".dsh")`.
  - `env_template_fragment="OCF_AGENT_TOOL=dsh\n"
    "OCF_GLOBAL_CONFIG_PATH={{OCF_GLOBAL_CONFIG_PATH}}\n"
    "OCF_GLOBAL_AUTH_PATH={{OCF_GLOBAL_AUTH_PATH}}"`.
  - `framework_config_subdir="dsh"`, `global_config_base="home"`,
    `global_config_is_dir=False`,
    `global_config_relpath=(".dsh", "settings.yaml")`,
    `global_env_relpath=(".dsh", ".env")`,
    `auth_relpath=(".dsh", ".credentials.yaml")`, `auth_base="home"`,
    `stub_relpath=("dsh", "stubs", "stub-credentials.yaml")` (per convention
    the single stub is the auth fallback; settings falls back to `/dev/null`
    — matches the opencode pattern; `config_files._generate_env_file` needs
    **no change** for this),
    `context_files=("AGENTS.md", "CLAUDE.md")`.
- Register in `SUPPORTED_TOOLS`. Update module docstring and
  `get_tool_spec` docstring ("opencode | qwen | dsh").
- Everything downstream (discovery, preflight, wizard branch naming, per-tool
  volume/image/container names, `--server` publish of 3080, launch
  precedence) is data-driven and needs no change.

### 2. `opencode_framework/agent/layers.py`

- `expected_global_auth_path(spec, data_home=None, home=None)`: when
  `spec.auth_base == "home"`, resolve `auth_relpath` against the `home`
  override or `get_local_home()`; otherwise keep data-home behavior
  (opencode unchanged).
- `discover_global_layer`: pass `home=home` into `expected_global_auth_path`.
- Adjust docstrings ("None for tools without an auth layer (qwen)…" stays
  true; mention base follows `auth_base`).

### 3. `opencode_framework/cli/app.py`

- `_print_version_info`: add a dsh block after the qwen one (settings found /
  path / expected path, plus credentials found / path / expected path),
  mirroring the existing style. Import `DSH_TOOL_SPEC`.
- Update the user-visible tool lists `"(opencode | qwen)"` in help/doc
  strings (~lines 279, 404, 416, 1013, 1027, 1036–1037, 1052) to
  `"(opencode | qwen | dsh)"`.
- No serve-flow change: `token_required=False` means no framework token is
  generated; dsh's own URL token appears in `docker compose run` output.

### 4. `opencode_framework/generators/templates.py`

- Add `_README_SECTIONS["dsh"]` (all five keys):
  - `models`: credentials via env (`DEEPSEEK_API_KEY`, injected through
    `.dsh/.env`, host `~/.dsh/.env`, or `launch -e`); provider/model entries
    via `settings.yaml` (`apiKeyEnv` refs, `llm-pi-ai` custom providers). Note
    `OCF_MAIN_MODEL`/`OCF_BUILD_MODEL`/`OCF_SMALL_MODEL` are **not wired** for
    dsh.
  - `install`: "Node.js 22 + `npm install -g @deepseek-ai/dsh` in the
    Dockerfile, version-pinned via the `OCF_AGENT_VERSION` build arg."
  - `config_layers`: table — Global: host `~/.dsh/settings.yaml` and
    `~/.dsh/.credentials.yaml`, mounted read-only at `~/.dsh/*` in the
    container; host `~/.dsh/.env` merged as lowest-priority launch env;
    `DEEPSEEK_API_KEY` via env wins over the credentials store. Framework:
    `web-bind-all.patch.yml` + `framework-nuts-and-bolts/{common,dsh}`.
    Project: this `.dsh/` worktree (`.env`, compose, `runtime_data/` =
    container home, so container `~/.dsh` profiles/sessions persist). Add:
    in-container Web UI saves to settings/credentials fail against the
    read-only mounts — edit on the host (dsh hot-reloads `settings.yaml`).
  - `serve`: dsh has **no TUI** — the Web UI is the interactive surface.
    `{{LAUNCH_COMMAND}} --server` publishes container port 3080 and runs
    `dsh web --no-open --port 3080 --patch
    /opt/ocframework/config/dsh/web-bind-all.patch.yml`; copy the
    `?token=…` value from the launch output and open
    `http://127.0.0.1:<host-port>/?token=…` (container port 3080 → host port
    may differ). Plain `launch` runs bare `dsh` and exits with a usage error —
    use `--server`, or pass through explicitly, e.g.
    `launch -- web --no-open` or `launch -- --profile headless "run tests"`.
  - `docs`: GitHub repo + docs site links.
- Update `agent_tool` docstrings in the render_* methods.

### 5. Framework content (new files)

- `framework-config/dsh/web-bind-all.patch.yml` — cordis patch-list overlay
  replacing the webserver row's config (`host: 0.0.0.0`, keep the `!!js` port
  expression so `--port` still wins, keep compression fields):

  ```yaml
  # OCF overlay: bind the dsh web server to all interfaces *inside the
  # sandbox* so docker port publishing reaches it. The dsh CLI rejects
  # `--host 0.0.0.0` by design; the webserver config row explicitly supports
  # it ("deliberate network exposure"). The UI still requires the one-time
  # ?token= URL printed at startup, and the container network is not
  # published unless you ask for it.
  - id: webserver
    name: '@deepseek-ai/dsh-host-webserver'
    config:
      host: 0.0.0.0
      port: !!js ctx.webStartup.port ?? 3080
      compression: gzip
      compressionLevel: 1
      compressionThresholdBytes: 1024
  ```

  If row targeting doesn't apply (verify with `--dump-config`; unmatched
  targets are reported on stderr), inspect
  `packages/bundle/web-app/cordis.patch.yml` semantics and adjust the
  selector keys — do not guess.
- `framework-config/dsh/stubs/stub-credentials.yaml` — content: `{}
  ` (empty YAML mapping).
- `framework-nuts-and-bolts/dsh/README.md` — short placeholder (directory must
  exist in-repo so the read-only mount resolves); list intended future
  contents (commands/MCP fragments) mirroring `qwen/`.

### 6. Docs

- `AGENTS.md`: CLI contract tool lists → `opencode | qwen | dsh`; registry
  description; env-var taxonomy — add tool-native `DSH_*`, `DEEPSEEK_API_KEY`,
  `DEEPSEEK_SEARCH_BASE_URL`; security model — dsh global/auth mounts
  (settings.yaml + .credentials.yaml RO, stub fallback), DSH_HOME under the
  RW runtime_data home; per-tool naming examples (`ocf_myrepo_dsh`,
  `codeagent-alice-dsh`); launch-detection coexistence text.
- `README.md` / `vision.md`: mention dsh wherever tools are listed.
- Cosmetic docstring sweep `(opencode | qwen)` → `| dsh` in
  `agent/discovery.py`, `sandbox/features.py`, `sandbox/compose.py`,
  `sandbox/devcontainer.py`, `sandbox/runtime.py`, `git_ops.py`,
  `generators/orchestrator.py`, `generators/config_files.py` and any other
  grep hits.

### 7. Tests (follow existing per-tool patterns)

- `tests/test_agent_registry.py`:
  - `TestDshSpec`: binary/config-dir; serve port 3080, `--no-open`, `--port`
    string present, `--patch` path pointing into `/opt/ocframework/config/dsh/`;
    `token_required is False` and `token_env == ""`; install `kind ==
    "dockerfile"`, snippet mentions `@deepseek-ai/dsh@${OCF_AGENT_VERSION}`;
    env line sets `DSH_HOME`; mounts include settings, `.credentials.yaml`,
    `framework-nuts-and-bolts/common` and `/dsh` under `.dsh`; global layer
    shape (home base, file, relpaths); `auth_relpath` + `auth_base == "home"`;
    `stub_relpath`; `context_files == ("AGENTS.md", "CLAUDE.md")`.
  - `SUPPORTED_TOOLS` has the three tools; `get_tool_spec("dsh")` works and
    the unsupported-name test still holds.
  - Defaults: `OPENCODE_TOOL_SPEC.auth_base == "data_home"`,
    `QWEN_TOOL_SPEC.auth_base == "data_home"`.
- `tests/test_agent_layers.py`: dsh auth path resolves under the injected
  `home` (not data home); `discover_global_layer` for dsh found/missing
  settings + credentials; stub fallback path.
- `tests/test_generator.py`: dsh README renders (serve section mentions 3080 +
  `--server`, excludes opencode/qwen wording); dsh `.env` render contains
  `OCF_AGENT_TOOL=dsh`, `OCF_GLOBAL_CONFIG_PATH`, `OCF_GLOBAL_AUTH_PATH`;
  compose render for dsh includes the DSH_HOME line and the two RO mounts;
  opencode/qwen compose renderings unchanged (still `command: ""`).
- `tests/test_cli.py`: launch help lists dsh; `--server` run command includes
  `--publish <host>:3080` and the web serve args; no auto token for dsh;
  status output includes the dsh lines; three-config discovery/prompt paths.
- `tests/test_wizard.py`: branch suggestion `codeagent-alice-dsh`.
- `tests/test_preflight.py`: `config_directory_exists(..., agent_tool="dsh")`
  checks `.dsh/`.

## Verification (definition of done)

```sh
poetry run ruff check . && poetry run ruff format . \
  && poetry run mypy opencode_framework/ && poetry run pytest
```

Manual smoke (requires docker + devcontainer CLIs; scratch git repo):

1. `ocframework init --tool dsh` → expect `.dsh/` worktree, `.env` with
   `OCF_AGENT_TOOL=dsh`, both `OCF_GLOBAL_*` keys, compose with DSH_HOME line +
   RO mounts + `framework-nuts-and-bolts/{common,dsh}`.
2. `ocframework launch --tool dsh` → bare `dsh` usage error (exit ≠ 0),
   documented behavior.
3. `ocframework launch --tool dsh --server` → server output prints
   `http://127.0.0.1:3080/?token=…`; from inside the container
   `dsh web --patch /opt/ocframework/config/dsh/web-bind-all.patch.yml
   --dump-config` shows the webserver row with `host: 0.0.0.0` (this is the
   go/no-go check for the patch overlay); browser at
   `http://127.0.0.1:<published-port>/?token=…` loads the UI.
4. With `DEEPSEEK_API_KEY` in host `~/.dsh/.env` (or `launch -e`), start a
   session and get a completion; verify `.credentials.yaml` stub mount doesn't
   shadow env keys and container `~/.dsh` profiles persist in
   `.dsh/runtime_data/`.
5. Second harness coexists: existing `.opencode/`/`.qwen/` untouched;
   `launch` with three configs prompts (TTY) or errors with `--tool`
   remediation (non-TTY).

## Risks / notes

- dsh is *developer preview* ("THERE WILL BE COMPATIBILITY-BREAKING CHANGES")
  — `OCF_AGENT_VERSION` pinning is the mitigation; smoke step 3 catches patch
  drift.
- dsh sandbox backends (bwrap/Landlock) inside the container may need
  `DSH_PERMISSION_MODE` tuning; if smoke step 4 hits it, document the var in
  the README config-layers section rather than changing the spec.
- Published npm package ships built web artifacts (root README's `npx
  @deepseek-ai/dsh web` flow) — no in-image build needed.
- Keep the investigation clone at `/tmp/opencode/dsh-src` if present; else
  re-clone sparse (`apps/cli packages/boot packages/bundle packages/host
  packages/util packages/settings packages/credentials`).
