# Git Storage Model

## Main Model

- `.opencode/` lives inside the target repository
- `.opencode/` is a nested linked Git worktree
- that worktree is used to version per-developer project config separately from the main project history

This is a hard v1 assumption.

## Branching Rules

- wizard suggests `codeagent-{username}` as the default branch name
- user chooses the final branch name
- if the branch exists, reuse it
- if the branch does not exist, create it as an orphan branch
- config branch is local by default
- pushing to remote is optional and user-controlled

## Main Branch Cleanliness

- no framework-specific committed traces should be added to the main project branch
- `.opencode/` may be ignored by the user manually, but the framework does not edit ignore config automatically

## Existing `.opencode/`

If `.opencode/` already exists for any reason:
- normal `init` exits with explanation
- `init --force` backs it up and replaces it

The framework does not try to distinguish between framework-managed and unrelated `.opencode/` content in v1.

## Backup Rule

Backup naming convention:
- `.opencode.backup-<timestamp>`

Backups are created at project root, not inside `.opencode/`.

## Worktree Ownership

The worktree stores:
- native project-level `opencode` config
- framework-generated devcontainer config
- local project runtime overrides
- local usage documentation

Mutable runtime state stays under `.opencode/runtime_data/` and is not intended for versioning.
