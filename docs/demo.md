# OpenCode Framework v1 - Business Acceptance Plan

## Prerequisites

- Git, Docker, devcontainer CLI, pipx installed
- `ocframework` command available in PATH
- A test directory for disposable repositories

---

## Scenario 1: Version and Help

**Purpose:** Verify CLI entrypoint works correctly.

```sh
ocframework
ocframework --version
ocframework --help
```

**Accept:**
- Bare command shows version info (not help, not error)
- `--version` shows: framework version, repo path, global config status, auth.json status
- `--help` shows only `init` command

---

## Scenario 2: Fresh Repository Init

**Purpose:** Verify happy path for new projects.

```sh
mkdir /tmp/demo-fresh && cd /tmp/demo-fresh
git init
git config user.email "demo@example.com"
git config user.name "Demo User"
echo "# Demo Project" > README.md
git add . && git commit -m "Initial commit"
ocframework init
```

Accept defaults, decline all optional features.

**Accept:**
- `.opencode/` directory created
- Worktree on `codeagent-{username}` branch
- Launch command printed: `ocframework launch`
- `git worktree list` shows two entries

---

## Scenario 3: Generated Files Verification

**Purpose:** Confirm output matches specification.

```sh
ls -la .opencode/
cat .opencode/devcontainer.json
cat .opencode/.gitignore
```

**Accept:**
- Files present: `devcontainer.json`, `.env`, `README.md`, `.gitignore`, `opencode.json`
- Directory present: `runtime_data/` with XDG subdirectories (`.cache`, `.local/share`, `.local/state`)
- `devcontainer.json` has: `image`, `features`, `workspaceFolder`, `mounts`, `postCreateCommand`, `postStartCommand`
- Global config mounted read-only (if present)

---

## Scenario 4: Force Regeneration with Backup

**Purpose:** Verify `--force` preserves existing work.

```sh
echo "important data" > .opencode/my-notes.txt
ocframework init --force
```

Accept defaults.

**Accept:**
- Backup created at `.opencode.backup-{timestamp}`
- `my-notes.txt` preserved in backup
- New `.opencode/` generated cleanly

---

## Scenario 5: Extend Existing Devcontainer

**Purpose:** Verify compatible devcontainer inheritance.

```sh
mkdir /tmp/demo-extend && cd /tmp/demo-extend
git init
git config user.email "demo@example.com"
git config user.name "Demo User"
mkdir .devcontainer
cat > .devcontainer/devcontainer.json << 'EOF'
{
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/python:1": {"version": "3.12"}
  },
  "customizations": {
    "vscode": {"extensions": ["ms-python.python"]}
  }
}
EOF
git add . && git commit -m "Initial commit"
ocframework init
```

Choose `extend` when prompted.

**Accept:**
- Original `image` preserved in generated config
- Original Python feature preserved
- VS Code extensions preserved
- Framework settings added (workspace, mounts, post commands)

---

## Scenario 6: Incompatible Devcontainer Rejection

**Purpose:** Verify safety guardrail for broken configs.

```sh
mkdir /tmp/demo-bad && cd /tmp/demo-bad
git init
git config user.email "demo@example.com"
git config user.name "Demo User"
mkdir .devcontainer
echo '{"name": "broken"}' > .devcontainer/devcontainer.json
git add . && git commit -m "Initial commit"
ocframework init
```

**Accept:**
- Clear error: "The existing devcontainer is incompatible: No 'image' or 'build' specified"
- Exit code 1
- No `.opencode/` created

---

## Scenario 7: Optional Features Selection

**Purpose:** Verify feature wiring.

```sh
mkdir /tmp/demo-features && cd /tmp/demo-features
git init
git config user.email "demo@example.com"
git config user.name "Demo User"
git commit --allow-empty -m "Initial commit"
ocframework init
```

Enable: Docker, Python, vi

**Accept:**
- `devcontainer.json` includes:
  - `docker-in-docker` feature with `enableNonRootDocker: true`
  - `python` feature with `installPoetry: true`
  - `common-utils` with `vim` in `installPackages`

---

## Scenario 8: Preflight Guardrails

**Purpose:** Verify safety checks prevent bad state.

**8a. Outside git repo:**
```sh
mkdir /tmp/notgit && cd /tmp/notgit
ocframework init
```
**Accept:** Error about not being in a git working tree

**8b. Not at repo root:**
```sh
cd /tmp/demo-fresh
mkdir subdir && cd subdir
ocframework init
```
**Accept:** Error about needing to run from repo root

**8c. Staged changes:**
```sh
cd /tmp/demo-fresh
echo "change" >> README.md
git add README.md
ocframework init
```
**Accept:** Error about staged changes

**8d. Existing .opencode without force:**
```sh
cd /tmp/demo-fresh
git reset HEAD README.md
ocframework init
```
**Accept:** Error about existing `.opencode/`, suggestion to use `--force`

---

## Scenario 9: Docker Rootless Validation

**Purpose:** Verify Docker feature safety check.

```sh
# Check if rootless context exists
docker context ls | grep rootless
```

If rootless context absent:
- Run `ocframework init`, enable Docker
- **Accept:** Warning shown, Docker not allowed without rootless context

If rootless context present:
- Run `ocframework init`, enable Docker
- **Accept:** Docker feature added
- Launch will use `DOCKER_CONTEXT=rootless` by default

---

## Scenario 10: Container Launch (Optional)

**Purpose:** Verify generated config actually works.

```sh
cd /tmp/demo-fresh
ocframework launch
```

**Accept:**
- Container builds/starts successfully
- Workspace mounted at `/workspace`
- Global config mounted read-only (if present)
- `opencode` auto-start attempted (may fail if not installed, expected)

**Cleanup:**

There is no `devcontainer down` flow yet. To stop and remove the container:

```sh
docker rm -f demo-fresh
```

---

## Sign-Off Checklist

| Scenario | Description | Pass/Fail | Notes |
|----------|-------------|-----------|-------|
| 1 | Version and Help | | |
| 2 | Fresh Repo Init | | |
| 3 | Generated Files | | |
| 4 | Force with Backup | | |
| 5 | Extend Devcontainer | | |
| 6 | Incompatible Rejection | | |
| 7 | Optional Features | | |
| 8a | Preflight: Not Git | | |
| 8b | Preflight: Not Root | | |
| 8c | Preflight: Staged | | |
| 8d | Preflight: Exists | | |
| 9 | Docker Rootless | | |
| 10 | Container Launch | | |

**Approver:** ________________

**Date:** ________________

**Comments:**

---

## Rollback Procedure

If acceptance fails:

1. Remove test directories: `rm -rf /tmp/demo-* /tmp/notgit`
2. Document failure with: command, expected, actual
3. File issue at project tracker
4. Await fix and re-run affected scenarios
