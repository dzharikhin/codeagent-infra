# CLI Contract

## Installation

The framework must be installed as an editable package from a git clone:

```sh
pipx install -e <path-to-framework-git-clone>
```

This is the only supported installation method. The framework repository is a required runtime asset.

## Commands in V1

- `init`
- `version` (via `--version` or bare command)

Both commands require a valid framework repository. If the framework repository is missing or invalid, all commands fail immediately with a clear error message.

## Framework Repository Requirements

A valid framework repository must contain:
- `.git/` directory
- `framework-nuts-and-bolts/` directory
- `framework-nuts-and-bolts/stub-auth.json` file
- `framework-config/` directory

If any required path is missing, the framework will not function.

## `version`

`version` prints only:
- framework version
- detected framework repo path
- whether global config was found
- global config path, if found
- whether global auth.json was found
- global auth.json path, if found

It does not print project-specific status in v1.

If the framework repository is invalid, version output shows the detected path with an INVALID marker and lists missing paths.

## `init` Preconditions

`init` must fail unless all of the following are true:
- framework is installed as editable from a valid git clone
- current directory is inside a Git working tree
- current directory is the repository root
- repository is not bare
- Git index has no staged changes

The following are not checked in v1:
- repo has commits
- repo has remote
- unstaged changes in the working tree
- untracked files
- detached HEAD

## `init` Flow

1. check required external tools
2. validate framework repository
3. validate current directory as a target repo
4. validate Git index has no staged changes
5. resolve framework repo location from the installed tool
6. autodetect global settings at canonical paths
7. inspect standard devcontainer files, if any
8. inspect whether `.opencode/` already exists
9. ask wizard questions
10. create or reuse the config branch and nested worktree at `.opencode/`
11. generate `.opencode/` contents
12. print launch instructions

## Required Tool Checks

Hard prerequisites include:
- `git`
- `docker`
- `devcontainer` (from `@devcontainers/cli`)
- `pipx`

Missing required tools cause:
- immediate failure
- no partial setup
- clear remediation instructions

## Global Settings Discovery

The framework discovers global settings in the **local user context** on the host machine, not in the container context.

### Local Context Resolution

Paths are resolved using this precedence:
1. `XDG_CONFIG_HOME` environment variable (if set)
2. `SUDO_USER`'s home directory (if running under sudo)
3. `HOME` environment variable
4. Current process user's home

This ensures that when running `ocframework init` as root or via sudo, the framework still operates in the actual user's context (e.g., `/home/jrx/.config/opencode` rather than `/root/.config/opencode`).

### Canonical Paths

- `$XDG_CONFIG_HOME/opencode` or `~/.config/opencode` - global config directory (host)
- `$XDG_DATA_HOME/opencode/auth.json` or `~/.local/share/opencode/auth.json` - global auth file (host)

### Behavior

- respects `XDG_CONFIG_HOME` and `XDG_DATA_HOME` environment variables if set
- falls back to `~/.config` and `~/.local/share` if XDG vars are not set
- uses local user context (SUDO_USER, HOME) for all host-side operations
- if global config directory exists, it is mounted read-only in the devcontainer
- if global auth.json exists, it is exposed read-only automatically

### Global Config Creation Prompt

**This is the first wizard question** if the global config directory does not exist.

If the global config directory does not exist, `init` prompts immediately:
- "Global config directory not found at: <path>"
- "Create global config directory? [Y/n]"

If the user accepts (default), the directory is created **in the local user's context** before any other setup steps.
If the user declines, no global config mount is added to `devcontainer.json`.

### Remote/Container Paths

The devcontainer uses separate paths for the container environment:
- `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, etc. in `.opencode/.env` define container-side paths
- These are independent of the host-side discovery paths
- `REMOTE_USER` in `.env` controls the container user (default: `root`)

## Wizard Questions

The wizard asks only for meaningful structural choices, in this order:

1. **Global config directory creation** (if missing) - asked FIRST before any other questions
2. Config branch name, with suggested default `codeagent-{username}`
3. Existing devcontainer strategy
4. Optional feature selection
5. Editor preference

The wizard also:
- checks `.gitignore`
- prints guidance if `.opencode` is not ignored
- does not edit ignore rules automatically

## Existing `.opencode/`

Normal mode:
- explain available options
- exit

`--force` mode:
- back up `.opencode/` to `.opencode.backup-<timestamp>` in project root
- regenerate from scratch

Invalid or incomplete `.opencode/` is handled the same way.

## Commit Behavior

- the framework never auto-commits generated config
- commit and push decisions stay with the developer

## Launch Output

After successful `init`, print:
- the exact CLI command to run: `ocframework launch`
- a short note that the generated devcontainer setup starts `opencode` automatically
