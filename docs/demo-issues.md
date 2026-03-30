# Demo Issues - Manual Testing Feedback

## Critical Blocker

**Source files missing from git:** The `src/` and `tests/` directories contain only `__pycache__/` directories. Python source files must be restored before fixes can be applied.

## Issues to Fix (in order)

### 1. Rename CLI from `ocf` to `ocframework`

**Current:** CLI entry point is `ocf`
**Expected:** CLI entry point should be `ocframework`
**Action:** Update `pyproject.toml` `[project.scripts]` section

```toml
[project.scripts]
ocframework = "opencode_framework.cli:main"
```

No deprecated `ocf` alias needed.

---

### 2. Replace `version` subcommand with `--version` flag

**Current:** `ocf version` prints version info
**Expected:** 
- `ocframework --version` prints version info
- `ocframework` (bare command) also prints version info
- Remove `version` as a subcommand

**Action:** Update CLI in `src/opencode_framework/cli.py` to use `--version` flag and handle bare command.

---

### 3. Simplify devcontainer wizard flow

**Current:** When no devcontainer exists, wizard asks if user wants to skip
**Expected:** When no devcontainer exists, automatically create from scratch (no skip question)

**Action:** Update `src/opencode_framework/wizard.py` to remove skip prompt and auto-create.

---

### 4. Show global auth.json in version output

**Current:** Version output does not show auth configuration
**Expected:** Detect and display global `auth.json` path if it exists:
- `~/.local/share/opencode/auth.json`

**Action:** Update `src/opencode_framework/config.py` and `cli.py` to detect and display auth file.

---

### 5. Fix ModuleNotFoundError for CLI imports

**Current:** `ModuleNotFoundError: No module named 'opencode_framework.cli'` when running from target repo
**Expected:** CLI works from any directory after installation

**Action:** 
- Ensure `pyproject.toml` has correct package configuration
- Verify `[project.scripts]` entry point path
- Ensure `src/` layout is properly configured with `package-dir`

---

## Verification Steps

After fixes:

1. Install: `pip install -e .`
2. Run: `ocframework` (should print version)
3. Run: `ocframework --version` (should print version)
4. Run: `ocframework --help` (should show help)
5. Run: `ocframework init` in a test repo (should work without import errors)
6. Test devcontainer auto-creation when none exists

## Files to Modify

| File | Changes |
|------|---------|
| `pyproject.toml` | Rename CLI, fix package config |
| `src/opencode_framework/cli.py` | `--version` flag, bare command, auth display |
| `src/opencode_framework/wizard.py` | Remove skip prompt, auto-create |
| `src/opencode_framework/config.py` | Detect auth.json |
| `tests/test_cli.py` | Update tests for new behavior |
