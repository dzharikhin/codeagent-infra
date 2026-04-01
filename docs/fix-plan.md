# Fix Plan - OpenCode Framework v1 Issues

## Issue Summary

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 13 | Create packaged devcontainer template for scratch generation | High | Completed |
| 14 | Create packaged .env template with defaults | High | Completed |
| 15 | Extend mode should merge only OpenCode-managed template fragments | High | Completed |
| 16 | Standardize sourced-env launch, debug, and shell commands | High | Completed |
| 17 | Update docs and tests to new template contract | High | Completed |
| 18 | Remove unused runtime_data subdirectories | Medium | Completed |
| 19 | Global config/auth/framework mounts must be read-only | High | Completed |
| 20 | Update .gitignore to ignore node_modules and remove .gitkeep unignore lines | Medium | Completed |
| 21 | Update framework docs URL to new location | Low | Completed |
| 22 | EDITOR variable from wizard should flow through .env | Medium | Completed |
| 23 | Remove DOCKER_CONTEXT from .env | Low | Completed |
| 24 | Add ocframework launch and exec CLI commands | High | Completed |

### Completed Historical Issues

Issues 1-5, 7, 12 were completed in earlier phases and are no longer relevant to current work.

### Superseded Issues

Issues 6, 8-11 were implemented but are now superseded by the template-driven approach (Issues 13-17).

---

## Issue 13: Create Packaged DevContainer Template for Scratch Generation

**Status:** Completed

**Current Behavior:**
- Scratch devcontainer is generated via inline Python dict construction
- Variable names use old `OCF_*` prefix
- No template file exists in package

**Expected Behavior:**
- Template file: `src/opencode_framework/templates/devcontainer.template.json`
- Template is packaged with the Python package
- Loaded via `importlib.resources`
- Generated scratch `devcontainer.json` matches template structure:
  - `$schema` key
  - `image` from `DEVCONTAINER_BASE_IMAGE` + `DEVCONTAINER_BASE_IMAGE_TAG`
  - `runArgs` with `--env-file ${localWorkspaceFolder}/.opencode/.env`
  - `workspaceMount` using `${localWorkspaceFolder}`
  - Runtime-data mounts for XDG cache/data/state
  - Global config/auth/framework mounts via `${localEnv:...}`
  - `remoteEnv` for `OPENCODE_CONFIG` and XDG vars
  - `containerUser` and `remoteUser` from `REMOTE_USER`
  - `postAttachCommand: "opencode --continue"`
- Optional features are added according to user selection but within template structure

**Variable Name Migrations:**
- `OCF_BASE_IMAGE` -> `DEVCONTAINER_BASE_IMAGE` + `DEVCONTAINER_BASE_IMAGE_TAG`
- `OCF_REMOTE_USER` -> `REMOTE_USER`
- `OCF_DOCKER_FEATURE_VERSION` -> `DOCKER_FEATURE_VERSION`

**Changes Required:**

### New Files
- `src/opencode_framework/templates/__init__.py` - Package marker
- `src/opencode_framework/templates/devcontainer.template.json` - DevContainer template

### pyproject.toml
- Add `[tool.setuptools.package-data]` section:
  ```toml
  [tool.setuptools.package-data]
  opencode_framework = ["templates/*"]
  ```

### generator.py
- New function `_load_devcontainer_template()` using `importlib.resources`:
  ```python
  from importlib.resources import files
  def _load_devcontainer_template() -> dict:
      content = files("opencode_framework.templates").joinpath("devcontainer.template.json").read_text()
      return json.loads(content)
  ```
- New function `_generate_scratch_from_template()` to populate template with:
  - Feature selection (add/remove features based on wizard)
  - Name substitution for project
- Remove `_generate_scratch_devcontainer()` inline dict construction

### config.py
- Ensure detected paths align with template variable expectations:
  - `OCF_LOCAL_GLOBAL_CONFIG_PATH`
  - `OCF_LOCAL_GLOBAL_AUTH_PATH`
  - `OCF_LOCAL_FRAMEWORK_PATH`

**Files:**
- `src/opencode_framework/templates/__init__.py` (new)
- `src/opencode_framework/templates/devcontainer.template.json` (new)
- `pyproject.toml`
- `src/opencode_framework/generator.py`
- `src/opencode_framework/config.py`
- `tests/test_generator.py`

---

## Issue 14: Create Packaged .env Template with Defaults

**Status:** Completed

**Current Behavior:**
- `.env` is generated as override-only with commented examples
- No hardcoded defaults
- Uses old `OCF_*` variable names
- No template file exists in package

**Expected Behavior:**
- Template file: `src/opencode_framework/templates/env.template`
- Template is packaged with the Python package
- Loaded via `importlib.resources`
- Generated `.opencode/.env` contains defaults (not override-only)
- Detected path values are filled in:
  - `OCF_LOCAL_GLOBAL_CONFIG_PATH`
  - `OCF_LOCAL_GLOBAL_AUTH_PATH`
  - `OCF_LOCAL_FRAMEWORK_PATH`
- Hardcoded defaults from template:
  - `DOCKER_CONTEXT=rootless`
  - `REMOTE_USER=root`
  - `XDG_CONFIG_HOME=/home/${REMOTE_USER:-root}/.config`
  - `XDG_DATA_HOME=/home/${REMOTE_USER:-root}/.local/share`
  - `XDG_STATE_HOME=/home/${REMOTE_USER:-root}/.local/state`
  - `XDG_CACHE_HOME=/home/${REMOTE_USER:-root}/.cache`
  - `OCF_REMOTE_FRAMEWORK_CONFIG_PATH=/opt/ocframework/config/config.json`
  - Model vars (`OCF_MAIN_MODEL`, `OCF_BUILD_MODEL`, `OCF_SMALL_MODEL`)

**Changes Required:**

### New Files
- `src/opencode_framework/templates/env.template` - Env template

### generator.py
- New function `_load_env_template()` using `importlib.resources`:
  ```python
  from importlib.resources import files
  def _load_env_template() -> str:
      return files("opencode_framework.templates").joinpath("env.template").read_text()
  ```
- Update `_generate_env_file()` to:
  - Load template
  - Fill detected path values using string replacement
  - Keep other defaults from template
- Remove override-only logic

### Tests
- Update all tests expecting commented/override-only `.env`
- Add tests for template-based `.env` generation

**Files:**
- `src/opencode_framework/templates/env.template` (new)
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Issue 15: Extend Mode Should Merge Only OpenCode-Managed Template Fragments

**Status:** Completed

**Current Behavior:**
- Extend mode rebuilds most of the devcontainer dict
- Preserves only `image`/`build`, existing features, and `remoteUser`
- May override project-specific settings

**Expected Behavior:**
- Extend mode preserves all existing project-specific config
- Adds only OpenCode-managed additions from template:
  - OpenCode feature (`ghcr.io/stu-bell/devcontainer-features/open-code:0`)
  - Selected optional features
  - Template `runArgs` (merge/deduplicate)
  - Runtime-data mounts (merge/deduplicate)
  - Global config/auth/framework mounts (merge/deduplicate)
  - Template `remoteEnv` (merge, project env takes precedence for non-OpenCode vars)
  - `postAttachCommand: "opencode --continue"`
- Preserves:
  - Existing `image` or `build`
  - Existing features (merged with OpenCode features)
  - Existing `remoteUser` / `containerUser`
  - Existing customizations
  - Any other project-specific settings

**Changes Required:**

### generator.py
- Refactor `_generate_extended_devcontainer()` to additive merge pattern
- New helper functions:
  - `_merge_features(existing, template_additions)`
  - `_merge_mounts(existing, template_additions)`
  - `_merge_run_args(existing, template_additions)`
  - `_merge_remote_env(existing, template_additions)`
- Preserve `postAttachCommand` from template (overwrite if exists)

### Tests
- Add tests for merge behavior
- Test deduplication of mounts/features
- Test preservation of existing settings

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Issue 16: Standardize Sourced-Env Launch, Debug, and Shell Commands

**Status:** Completed

**Current Behavior:**
- Launch command is rendered with/without `DOCKER_CONTEXT=rootless` prefix
- `DOCKER_CONTEXT` handling is in command rendering logic
- No debug or shell command examples

**Expected Behavior:**
- All commands source `.opencode/.env` before execution
- `DOCKER_CONTEXT` comes from `.env`, not command rendering
- Launch command:
  ```sh
  set -o allexport; source .opencode/.env; devcontainer up --config .opencode/devcontainer.json --workspace-folder .
  ```
- Debug command:
  ```sh
  set -o allexport; source .opencode/.env; devcontainer exec --config .opencode/devcontainer.json --workspace-folder . opencode debug config
  ```
- Shell command:
  ```sh
  set -o allexport; source .opencode/.env; devcontainer exec --config .opencode/devcontainer.json --workspace-folder . $(devcontainer exec --config .opencode/devcontainer.json --workspace-folder . grep $REMOTE_USER /etc/passwd | cut -d: -f7)
  ```

**Changes Required:**

### generator.py
- Remove `_get_launch_command()` conditional Docker context logic
- New function `_get_launch_commands()` returning dict:
  - `launch`
  - `debug`
  - `shell`
- All commands use `set -o allexport; source .opencode/.env;` prefix

### cli.py
- Update output to show all three commands

### README template
- Update to show all three commands with explanations

### Tests
- Remove tests for conditional Docker context rendering
- Add tests for sourced-env command format

**Files:**
- `src/opencode_framework/generator.py`
- `src/opencode_framework/cli.py`
- `tests/test_generator.py`
- `tests/test_cli.py`

---

## Issue 17: Update Docs and Tests to New Template Contract

**Status:** Completed

**Current Behavior:**
- Tests assert old variable names (`OCF_*`)
- Tests assert override-only `.env` behavior
- Tests assert conditional Docker context launch commands
- Docs reference old variable names and commands

**Expected Behavior:**
- All tests use new variable names
- Tests validate template-driven generation
- Tests validate sourced-env commands
- Docs updated to reflect template approach

**Changes Required:**

### Tests
- `tests/test_generator.py`:
  - Update all variable name assertions
  - Update `.env` generation tests
  - Update devcontainer structure tests
  - Update launch command tests
  - Add template-based generation tests
- `tests/test_cli.py`:
  - Update output assertions
- `tests/test_integration.py`:
  - Update integration tests

### Documentation
- `docs/demo.md`:
  - Update variable names
  - Update launch commands
- `docs/security-model.md`:
  - Update Docker context references
- `docs/devcontainer-strategy.md`:
  - Update launch commands
  - Update variable references
- `docs/implementation-plan-v1.md`:
  - Note as historical reference

**Files:**
- `tests/test_generator.py`
- `tests/test_cli.py`
- `tests/test_integration.py`
- `docs/demo.md`
- `docs/security-model.md`
- `docs/devcontainer-strategy.md`

---

## Issue 18: Remove Unused Runtime Data Subdirectories

**Status:** Completed

**Current Behavior:**
- `_generate_runtime_data()` creates many subdirectories under `.opencode/runtime_data/`:
  - `.cache`
  - `.local/share`
  - `.local/state`
  - `logs`
  - `tools`
  - `temp`
  - `sessions`
  - `output`
  - `home`
- Only `.cache`, `.local/share`, and `.local/state` are actually mounted in the devcontainer template
- Other directories are never used
- A root-level `runtime_data/.gitkeep` is created

**Expected Behavior:**
- Only create XDG-backed directories that are actually used:
  - `.opencode/runtime_data/.cache/`
  - `.opencode/runtime_data/.local/share/`
  - `.opencode/runtime_data/.local/state/`
- Remove creation of unused directories:
  - `logs`
  - `tools`
  - `temp`
  - `sessions`
  - `output`
  - `home`
- Add `.gitkeep` files only in directories confirmed to be in use (the 3 XDG dirs)
- Update generated `.opencode/.gitignore` to allow `.gitkeep` files in kept directories to be committed
- Remove root-level `runtime_data/.gitkeep`

**Rationale:**
- Devcontainer template only mounts the XDG cache/data/state directories
- Unused directories add clutter and confusion
- `.gitkeep` should only exist where we have confirmed usage
- Keeps runtime data structure aligned with actual mount configuration

**Changes Required:**

### generator.py
- Update `_generate_runtime_data()` to create only:
  - `.cache/`
  - `.local/share/`
  - `.local/state/`
- Remove creation of:
  - `logs/`
  - `tools/`
  - `temp/`
  - `sessions/`
  - `output/`
  - `home/`
- Remove root-level `runtime_data/.gitkeep`
- Create `.gitkeep` in each of the 3 kept directories:
  - `.opencode/runtime_data/.cache/.gitkeep`
  - `.opencode/runtime_data/.local/share/.gitkeep`
  - `.opencode/runtime_data/.local/state/.gitkeep`
- Possibly update `.gitignore` generation to permit these `.gitkeep` files

### Tests
- Update `tests/test_generator.py`:
  - Assert only 3 kept directories are created
  - Assert removed directories are absent
  - Assert `.gitkeep` exists in kept directories
  - Assert root-level `runtime_data/.gitkeep` is not created

### Documentation
- `docs/runtime-layout.md`:
  - Remove references to unused directories
  - Document only the 3 XDG-backed directories
- `docs/demo.md`:
  - Update expected runtime_data structure
- Other docs as needed

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`
- `docs/runtime-layout.md`
- `docs/demo.md`

---

## Issue 19: Global Config/Auth/Framework Mounts Must Be Read-Only

**Status:** Completed

**Current Behavior:**
- Template mounts use object/dict format with `"readOnly": true`
- devcontainer CLI/toolchain may not enforce readOnly on dict mounts
- User testing showed global `auth.json` was editable from inside container

**Expected Behavior:**
- Global config directory mounted read-only
- Global `auth.json` file mounted read-only
- Framework config file mounted read-only
- Use Docker mount string syntax with `readonly` flag for reliable enforcement
- Runtime data mounts (cache, data, state) remain read-write

**Changes Required:**

### devcontainer.template.json
- Convert all mounts from dict format to string format
- Runtime data mounts: `type=bind,source=...,target=...`
- Global config/auth/framework mounts: `type=bind,source=...,target=...,readonly`

### generator.py
- Add `_extract_mount_target()` helper to parse target from string or dict mounts
- Update `_merge_mounts()` to handle both string and dict mounts
- Deduplicate by target path regardless of mount format

### Tests
- Add tests for `_extract_mount_target()` with both formats
- Add tests for `_merge_mounts()` with string, dict, and mixed mounts
- Add tests asserting `readonly` in global config mount string
- Add tests asserting `readonly` in global auth mount string
- Add tests asserting `readonly` in framework config mount string

**Files:**
- `src/opencode_framework/templates/devcontainer.template.json`
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Issue 20: Update .gitignore to Ignore node_modules and Remove .gitkeep Unignore Lines

**Status:** Completed

**Current Behavior:**
- Generated `.opencode/.gitignore` ignores `runtime_data/*`
- Contains explicit unignore lines for `.gitkeep` files in runtime subdirs:
  ```
  !runtime_data/.cache/.gitkeep
  !runtime_data/.local/share/.gitkeep
  !runtime_data/.local/state/.gitkeep
  ```
- Does not ignore `node_modules/` directory (created by `bun install` for OpenCode plugins)
- Both `.gitkeep` files and their unignore rules are generated

**Expected Behavior:**
- Add `node_modules/` to generated `.gitignore`
- Remove `.gitkeep` unignore lines from `.gitignore`
- Optionally stop generating `.gitkeep` files entirely (decision pending)

**Rationale:**
- `node_modules/` is created by `bun install` when OpenCode installs plugins/tools locally
- These artifacts should not be committed to the repository
- `.gitkeep` files are unnecessary if the directories are gitignored anyway
- Simplifies gitignore rules

**Changes Required:**

### generator.py
- Update `.gitignore` generation in `_generate_opencode_dir()`:
  - Add `node_modules/` to ignored patterns
  - Remove lines that unignore `.gitkeep` files
- Optionally update `_generate_runtime_data()` to stop creating `.gitkeep` files

### Tests
- Update `tests/test_generator.py`:
  - Assert `node_modules/` is present in `.gitignore`
  - Assert `.gitkeep` unignore lines are absent
  - If `.gitkeep` generation is removed, update runtime data tests accordingly

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Issue 21: Update Framework Docs URL to New Location

**Status:** Completed

**Current Behavior:**
- Generated `.opencode/README.md` references old framework URL:
  - `https://github.com/anomalyco/opencode-framework`

**Expected Behavior:**
- Update to new framework URL:
  - `https://github.com/dzharikhin/codeagent-infra`

**Rationale:**
- Framework documentation has moved to new repository
- Users should be directed to correct location

**Changes Required:**

### generator.py
- Update `_generate_readme()` to use new URL

### Tests
- Update `tests/test_generator.py` README assertion to check for new URL

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Issue 22: EDITOR Variable Flow Through .env

**Status:** Completed

**Current Behavior:**
- Wizard captures `editor_choice` ("none", "vi", or "nano")
- `remoteEnv["EDITOR"]` in devcontainer.json is set to literal value (e.g., "vi")
- EDITOR is not written to `.opencode/.env`

**Expected Behavior:**
- When `editor_choice` is "vi" or "nano":
  - Write `EDITOR=vi` or `EDITOR=nano` to `.opencode/.env`
  - Set `remoteEnv["EDITOR"] = "${localEnv:EDITOR}"` in devcontainer.json
- When `editor_choice` is "none":
  - Do not write EDITOR to `.opencode/.env`
  - Do not set EDITOR in remoteEnv

**Rationale:**
- `.env` should be the single source of truth for runtime configuration
- Allows users to easily change EDITOR without regenerating devcontainer
- Consistent with other env-driven configuration like REMOTE_USER

**Changes Required:**

### generator.py
- Update `_generate_env_file()` to append `EDITOR=<choice>` when choice is not "none"
- Update `_generate_scratch_devcontainer()` to use `${localEnv:EDITOR}` instead of literal
- Update `_generate_extended_devcontainer()` to use `${localEnv:EDITOR}` instead of literal

### Tests
- Add tests for EDITOR in `.env` file when selected
- Add tests for EDITOR omitted when choice is "none"
- Add tests for `remoteEnv["EDITOR"]` using `${localEnv:EDITOR}`

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`
- `tests/test_integration.py`

---

## Issue 23: Remove DOCKER_CONTEXT from .env

**Status:** Completed

**Current Behavior:**
- `DOCKER_CONTEXT=rootless` is present in `env.template`
- Generated `.opencode/.env` includes `DOCKER_CONTEXT=rootless`

**Expected Behavior:**
- Remove `DOCKER_CONTEXT` from `env.template`
- Generated `.opencode/.env` should not include `DOCKER_CONTEXT`

**Rationale:**
- `DOCKER_CONTEXT` is not actually used by the devcontainer runtime
- It was a leftover from earlier design decisions
- Removing it simplifies the `.env` file

**Changes Required:**

### env.template
- Remove `DOCKER_CONTEXT=rootless` line

### Tests
- Remove test that asserts `DOCKER_CONTEXT=rootless` in `.env`

**Files:**
- `src/opencode_framework/templates/env.template`
- `tests/test_generator.py`

---

## Issue 24: Add ocframework launch and exec CLI Commands

**Status:** Pending

**Current Behavior:**
- `_get_launch_commands()` in `generator.py` returns shell snippets that `source .opencode/.env`
- `DOCKER_CONTEXT` was removed from `.env`, so old shell snippets are incomplete
- Generated README still prints old shell-based commands
- No first-class CLI commands for `launch` or `exec`
- Docs still reference raw `devcontainer up` / `devcontainer exec` commands

**Expected Behavior:**
- New CLI command: `ocframework launch`
  - Validates: inside Git tree, at repo root, `.opencode/` exists, `.opencode/devcontainer.json` exists, `.opencode/.env` exists
  - Loads `.opencode/.env` and expands `${VAR}` and `${VAR:-default}` syntax
  - Sets `DOCKER_CONTEXT=rootless` in subprocess env by default
  - Supports `--docker-context <name>` to override
  - Runs: `devcontainer up --config .opencode/devcontainer.json --workspace-folder .`
  - Exits with subprocess return code
- New CLI command: `ocframework exec`
  - Same validation and env setup as `launch`
  - Supports `--docker-context <name>` to override
  - Requires `--` before inner command
  - Runs: `devcontainer exec --config .opencode/devcontainer.json --workspace-folder . <command...>`
  - Example: `ocframework exec --docker-context myctx -- opencode debug config`
- Updated generated commands in `_get_launch_commands()`:
  - `launch` -> `ocframework launch`
  - `debug` -> `ocframework exec -- opencode debug config`
  - `shell` -> `ocframework exec -- bash`
- Updated generated README to show new CLI commands
- Updated docs to promote CLI-first workflow:
  - `docs/devcontainer-strategy.md`
  - `docs/demo.md`
  - `docs/security-model.md`
  - Leave `docs/implementation-plan-v1.md` as historical reference

**Rationale:**
- `.opencode/.env` uses shell-style expansion (`${REMOTE_USER:-root}`), so simple key=value parsing won't work
- CLI commands can properly expand env vars and inject `DOCKER_CONTEXT` for the subprocess only
- CLI-first UX is more reliable than expecting users to `source` shell scripts
- Separates framework concerns from user shell environment

**Changes Required:**

### src/opencode_framework/cli.py
- Add `launch` command:
  - Import shared helpers from new `runtime.py` module
  - Validate repo root and required files
  - Load and expand `.opencode/.env`
  - Build subprocess env with `DOCKER_CONTEXT` (default `rootless`, override via `--docker-context`)
  - Run `devcontainer up` with computed env
  - Exit with subprocess return code
- Add `exec` command:
  - Reuse same validation and env setup as `launch`
  - Parse `--` and following args as inner command
  - Run `devcontainer exec` with computed env and inner command
  - Exit with subprocess return code

### src/opencode_framework/runtime.py (new)
- `validate_runtime_context(cwd: Path) -> tuple[bool, str]`
  - Check: inside Git tree
  - Check: at repo root
  - Check: `.opencode/` exists
  - Check: `.opencode/devcontainer.json` exists
  - Check: `.opencode/.env` exists
  - Return `(True, "")` on success, `(False, "error message")` on failure
- `load_and_expand_env(env_path: Path) -> dict[str, str]`
  - Parse `.env` file
  - Expand `${VAR}` references using already-parsed vars
  - Expand `${VAR:-default}` syntax
  - Return dict of expanded key-value pairs
- `build_devcontainer_env(base_env: dict[str, str], docker_context: str) -> dict[str, str]`
  - Merge base_env with current process env
  - Set `DOCKER_CONTEXT=docker_context`
  - Return env dict for subprocess

### src/opencode_framework/generator.py
- Update `_get_launch_commands()` to return CLI-based commands:
  ```python
  return {
      "launch": "ocframework launch",
      "debug": "ocframework exec -- opencode debug config",
      "shell": "ocframework exec -- bash",
  }
  ```
- Update `_generate_readme()` command descriptions if needed

### src/opencode_framework/preflight.py
- No changes required (existing Git/repo-root checks are sufficient for `init`)
- `runtime.py` will have its own lighter-weight checks for `launch`/`exec`

### Tests
- `tests/test_runtime.py` (new):
  - `test_validate_runtime_context_success`
  - `test_validate_runtime_context_not_git_tree`
  - `test_validate_runtime_context_not_repo_root`
  - `test_validate_runtime_context_missing_opencode_dir`
  - `test_validate_runtime_context_missing_devcontainer_json`
  - `test_validate_runtime_context_missing_env_file`
  - `test_load_and_expand_env_simple`
  - `test_load_and_expand_env_var_expansion`
  - `test_load_and_expand_env_default_expansion`
  - `test_load_and_expand_env_nested_expansion`
  - `test_build_devcontainer_env_docker_context_default`
  - `test_build_devcontainer_env_docker_context_override`
- `tests/test_cli.py`:
  - `test_launch_requires_git_repo`
  - `test_launch_requires_repo_root`
  - `test_launch_requires_opencode_dir`
  - `test_launch_requires_devcontainer_json`
  - `test_launch_requires_env_file`
  - `test_launch_docker_context_default`
  - `test_launch_docker_context_override`
  - `test_exec_requires_double_dash`
  - `test_exec_passes_command_args`
- `tests/test_generator.py`:
  - Update `TestLaunchCommands` to expect CLI commands
  - Update `TestReadmeLaunchCommand` to expect CLI commands

### Documentation
- `docs/devcontainer-strategy.md`:
  - Update "Canonical Launch Command" section to show `ocframework launch`
- `docs/demo.md`:
  - Replace raw `devcontainer up` commands with `ocframework launch`
  - Replace `DOCKER_CONTEXT=rootless` references with CLI override examples
- `docs/security-model.md`:
  - Remove statement about generated config wiring `DOCKER_CONTEXT=rootless`
  - Clarify that `DOCKER_CONTEXT` is set by CLI for subprocess only

**Files:**
- `src/opencode_framework/cli.py`
- `src/opencode_framework/runtime.py` (new)
- `src/opencode_framework/generator.py`
- `tests/test_runtime.py` (new)
- `tests/test_cli.py`
- `tests/test_generator.py`
- `docs/devcontainer-strategy.md`
- `docs/demo.md`
- `docs/security-model.md`

---

## Implementation Order

```
Phase 1: Template Package Setup
├── Create src/opencode_framework/templates/__init__.py
├── Create src/opencode_framework/templates/devcontainer.template.json
├── Create src/opencode_framework/templates/env.template
└── Update pyproject.toml with package-data

Phase 2: Template Loading
├── 13.1: Implement _load_devcontainer_template() with importlib.resources
├── 14.1: Implement _load_env_template() with importlib.resources
└── 14.2: Fill detected path values in .env template

Phase 3: Scratch Generation
├── 13.2: Populate template with detected values
└── 13.3: Feature selection within template

Phase 4: Extend Mode
├── 15.1: Refactor to additive merge pattern
└── 15.2: Implement merge helpers

Phase 5: Commands
├── 16.1: Update launch command generation
└── 16.2: Add debug and shell commands

Phase 6: Tests and Docs
├── 17.1: Update tests
└── 17.2: Update documentation

Phase 7: Validation
├── Verify template files are packaged correctly
├── Test importlib.resources loading works from installed package
├── Test extend mode preserves project settings
├── Verify sourced-env commands work
└── Full test suite passes

Phase 8: Launch/Exec CLI Commands
├── 24.1: Create src/opencode_framework/runtime.py with validation and env helpers
├── 24.2: Implement load_and_expand_env() with ${VAR} and ${VAR:-default} expansion
├── 24.3: Add ocframework launch command to cli.py
├── 24.4: Add ocframework exec command to cli.py
├── 24.5: Update _get_launch_commands() to return CLI-based commands
├── 24.6: Update generated README to show CLI commands
├── 24.7: Add tests for runtime.py helpers
├── 24.8: Add tests for launch and exec CLI commands
├── 24.9: Update generator tests for new CLI commands
├── 24.10: Update docs for CLI-first workflow
└── Full test suite passes
```

---

## Acceptance Criteria

### 13. Packaged DevContainer Template
- [x] `src/opencode_framework/templates/devcontainer.template.json` exists
- [x] Template is included in package build
- [x] Template loaded via `importlib.resources`
- [x] Generated scratch devcontainer matches template structure
- [x] `$schema` present
- [x] `runArgs` includes env-file
- [x] Runtime-data XDG mounts present
- [x] Uses `DEVCONTAINER_BASE_IMAGE` and `DEVCONTAINER_BASE_IMAGE_TAG`
- [x] Uses `REMOTE_USER` for user config
- [x] `postAttachCommand: "opencode --continue"`

### 14. Packaged Env Template
- [x] `src/opencode_framework/templates/env.template` exists
- [x] Template is included in package build
- [x] Template loaded via `importlib.resources`
- [x] Generated `.env` matches template structure
- [x] Contains defaults (not override-only)
- [x] Detected paths filled in

### 15. Extend Mode Merge
- [x] Preserves existing `image`/`build`
- [x] Preserves existing features (merged)
- [x] Adds only OpenCode-managed additions
- [x] Deduplicates mounts and runArgs

### 16. Sourced-Env Commands
- [x] Launch command sources `.opencode/.env`
- [x] Debug command sources `.opencode/.env`
- [x] Shell command sources `.opencode/.env`
- [x] README shows all three commands

### 17. Tests and Docs
- [x] All tests use new variable names
- [x] Tests pass
- [x] Docs updated to template approach

### 18. Runtime Data Cleanup
- [x] `_generate_runtime_data()` creates only `.cache/`, `.local/share/`, `.local/state/`
- [x] Unused directories (`logs`, `tools`, `temp`, `sessions`, `output`, `home`) not created
- [x] Root-level `runtime_data/.gitkeep` removed
- [x] `.gitkeep` files created in each kept directory
- [x] `.gitignore` permits `.gitkeep` files in kept directories
- [x] Tests updated to assert correct directory structure
- [x] `docs/runtime-layout.md` updated
- [x] `docs/demo.md` updated
- [x] Full test suite passes

### 19. Read-Only Mounts
- [x] Template mounts converted to string format
- [x] Global config mount includes `readonly`
- [x] Global auth mount includes `readonly`
- [x] Framework config mount includes `readonly`
- [x] `_merge_mounts()` handles string mounts
- [x] Tests for mount target extraction
- [x] Tests for mount merging with mixed formats
- [x] Tests asserting `readonly` in RO mount strings
- [x] Full test suite passes

### 20. Gitignore Cleanup
- [x] `node_modules/` added to generated `.gitignore`
- [x] `.gitkeep` unignore lines removed from `.gitignore`
- [x] `.gitkeep` files no longer generated in runtime_data
- [x] Tests updated to assert new gitignore content
- [x] Full test suite passes

### 21. Framework Docs URL Update
- [x] Generated README uses new URL `https://github.com/dzharikhin/codeagent-infra`
- [x] Tests updated to assert new URL
- [x] Full test suite passes

### 22. EDITOR Variable Flow Through .env
- [x] `EDITOR` written to `.opencode/.env` when editor_choice is "vi" or "nano"
- [x] `EDITOR` omitted from `.opencode/.env` when editor_choice is "none"
- [x] `remoteEnv["EDITOR"]` uses `${localEnv:EDITOR}` instead of literal value
- [x] Tests for EDITOR in .env file
- [x] Tests for remoteEnv using localEnv reference
- [x] Full test suite passes

### 23. Remove DOCKER_CONTEXT from .env
- [x] `DOCKER_CONTEXT` removed from `env.template`
- [x] Test for `DOCKER_CONTEXT` in `.env` removed
- [x] Full test suite passes

### 24. Launch and Exec CLI Commands
- [x] `src/opencode_framework/runtime.py` exists with validation and env helpers
- [x] `validate_runtime_context()` checks Git tree, repo root, `.opencode/`, devcontainer.json, .env
- [x] `load_and_expand_env()` expands `${VAR}` and `${VAR:-default}` syntax
- [x] `build_devcontainer_env()` sets `DOCKER_CONTEXT` with default and override
- [x] `ocframework launch` command exists in CLI
- [x] `launch` validates runtime context before running
- [x] `launch` loads and expands `.opencode/.env`
- [x] `launch` sets `DOCKER_CONTEXT=rootless` by default for subprocess
- [x] `launch --docker-context <name>` overrides Docker context
- [x] `launch` runs `devcontainer up` and exits with subprocess code
- [x] `ocframework exec` command exists in CLI
- [x] `exec` validates runtime context before running
- [x] `exec --docker-context <name>` overrides Docker context
- [x] `exec` requires `--` before inner command
- [x] `exec` runs `devcontainer exec` with inner command and exits with subprocess code
- [x] `_get_launch_commands()` returns CLI-based commands
- [x] Generated README shows CLI commands
- [x] `docs/devcontainer-strategy.md` updated for CLI-first workflow
- [x] `docs/demo.md` updated with CLI examples
- [x] `docs/security-model.md` updated to remove `DOCKER_CONTEXT` config statement
- [x] Unit tests for env expansion pass
- [x] CLI tests for launch/exec pass
- [x] Generator tests updated for CLI commands
- [x] Full test suite passes

---

## Variable Name Migration Reference

| Old Name | New Name | Location |
|----------|----------|----------|
| `OCF_BASE_IMAGE` | `DEVCONTAINER_BASE_IMAGE` + `DEVCONTAINER_BASE_IMAGE_TAG` | devcontainer.json, .env |
| `OCF_REMOTE_USER` | `REMOTE_USER` | devcontainer.json, .env |
| `OCF_DOCKER_FEATURE_VERSION` | `DOCKER_FEATURE_VERSION` | devcontainer.json, .env |
| `OCF_PYTHON_VERSION` | `PYTHON_VERSION` | (if needed) |
| `OCF_NODE_VERSION` | `NODE_VERSION` | (if needed) |
| `OCF_JAVA_VERSION` | `JAVA_VERSION` | (if needed) |

---

## Template Files (Package-Internal)

- `src/opencode_framework/templates/devcontainer.template.json` - DevContainer template for scratch generation
- `src/opencode_framework/templates/env.template` - Env template with defaults
