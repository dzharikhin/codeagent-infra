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

It does not print project-specific status in v1.

## `init` Preconditions

`init` must fail unless all of the following are true:
- current directory is inside a Git working tree
- current directory is the repository root
- repository is not bare

The following are not checked in v1:
- repo has commits
- repo has remote
- working tree cleanliness
- staged changes
- detached HEAD

## `init` Flow

1. check required external tools
2. validate current directory as a target repo
3. resolve framework repo location from the installed tool
4. inspect global config path
5. inspect standard devcontainer files, if any
6. inspect whether `.opencode/` already exists
7. ask wizard questions
8. create or reuse the config branch and nested worktree at `.opencode/`
9. generate `.opencode/` contents
10. print launch instructions

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

## Global Config Discovery

Standard lookup path:
- `~/.config/opencode`

Behavior:
- if the path exists, validate it and ask whether to use or ignore it
- if the path does not exist, ask whether to skip global config or provide a path manually

## Wizard Questions

The wizard asks only for meaningful structural choices:
- config branch name, with suggested default `codeagent-{username}`
- whether to use or ignore global config
- existing devcontainer strategy
- optional feature selection
- framework/global paths if they cannot be resolved confidently

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
