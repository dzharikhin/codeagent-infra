# CLI Contract

## Commands in V1

- `init`
- `version`

`version` is the only command that must work outside a project repository.

## `version`

`version` prints only:
- framework version
- detected framework repo path
- whether global config was found
- global config path, if found
- whether global auth.json was found
- global auth.json path, if found

It does not print project-specific status in v1.

## `init` Preconditions

`init` must fail unless all of the following are true:
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
2. validate current directory as a target repo
3. validate Git index has no staged changes
4. resolve framework repo location from the installed tool
5. autodetect global settings at canonical paths
6. inspect standard devcontainer files, if any
7. inspect whether `.opencode/` already exists
8. ask wizard questions
9. create or reuse the config branch and nested worktree at `.opencode/`
10. generate `.opencode/` contents
11. print launch instructions

## Required Tool Checks

Hard prerequisites include:
- `git`
- `docker`
- `devcontainer-cli`
- `pipx`

Missing required tools cause:
- immediate failure
- no partial setup
- clear remediation instructions

## Global Settings Discovery

The framework uses fixed canonical paths for global settings:
- `~/.config/opencode` - global config directory
- `~/.local/share/opencode/auth.json` - global auth file

Behavior:
- if `~/.config/opencode` exists, use it automatically
- if `~/.local/share/opencode/auth.json` exists, expose it automatically
- if either is absent, continue without it
- no user prompts about global settings location or creation

## Wizard Questions

The wizard asks only for meaningful structural choices:
- config branch name, with suggested default `codeagent-{username}`
- existing devcontainer strategy
- optional feature selection

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
- the exact `devcontainer` command to run
- a short note that the generated devcontainer setup starts `opencode` automatically
