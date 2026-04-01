# Fix Plan - OpenCode Framework v1 Issues

## Issue Summary

| # | Issue | Priority | Status |
|---|-------|----------|--------|
| 13 | Create packaged devcontainer template for scratch generation | High | Completed |
| 14 | Create packaged .env template with defaults | High | Completed |
| 15 | Extend mode should merge only OpenCode-managed template fragments | High | Completed |
| 16 | Standardize sourced-env launch, debug, and shell commands | High | Completed |
| 17 | Update docs and tests to new template contract | High | Completed |

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
- [x] `DOCKER_CONTEXT=rootless` in `.env`

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
