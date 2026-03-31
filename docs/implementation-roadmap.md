# Implementation Roadmap

## Goal

Implement v1 in small execution units that a coding agent can complete incrementally.

## Phase 1 - CLI Skeleton

Deliver:
- Python package scaffold
- `init` and `version` command stubs
- framework self-location logic

Tasks:
1. create Python package layout
2. wire CLI entrypoint for `pipx`
3. implement `version` output contract
4. add basic tests for command availability and output shape

Acceptance criteria:
- `version` works outside a project
- output contains only the agreed global/framework fields

## Phase 2 - Preflight and Repo Validation

Deliver:
- required tool checks
- repo-root validation
- clean index validation
- global settings autodetection logic

Tasks:
1. implement external tool detection for hard prerequisites
2. implement Git working tree, repo-root, and non-bare checks
3. implement Git index cleanliness check (no staged changes)
4. implement standard global config detection at `~/.config/opencode`
5. implement global auth detection at `~/.local/share/opencode/auth.json`
6. implement remediation-oriented error formatting
7. add tests for failure modes and success path

Acceptance criteria:
- `init` fails early and clearly when prerequisites are not met
- `init` refuses unsupported repo entrypoints
- `init` fails with clear guidance when index has staged changes

## Phase 3 - `.opencode` Git Storage Model

Deliver:
- branch naming suggestion
- branch reuse/create flow
- orphan-branch creation for new config branches
- nested worktree creation at `.opencode/`

Tasks:
1. implement username-based branch suggestion
2. implement branch existence detection
3. implement orphan-branch creation for new branches
4. implement linked worktree creation at `.opencode/`
5. add tests covering reuse vs create behavior

Acceptance criteria:
- a new repo can receive a fresh `.opencode/` worktree
- an existing branch can be reused without altering the main branch

## Phase 4 - Existing State and `--force`

Deliver:
- detection of existing `.opencode/`
- backup behavior
- regenerate-from-scratch flow

Tasks:
1. detect existing `.opencode/` before materialization
2. implement normal-mode exit behavior with clear next steps
3. implement `.opencode.backup-<timestamp>` backup creation
4. implement full regeneration path behind `--force`
5. add tests for backup and regeneration

Acceptance criteria:
- existing `.opencode/` never gets overwritten in normal mode
- `--force` always creates a backup before replacement

## Phase 5 - Wizard and Decision Collection

Deliver:
- interactive question flow for structural decisions

Tasks:
1. ask for branch name with suggested default
2. ask for devcontainer strategy when standard devcontainer exists
3. ask for optional feature selection
4. print `.gitignore` guidance when `.opencode` is not ignored

Acceptance criteria:
- wizard asks only the agreed decision points
- answers are sufficient to drive generation without extra prompts

## Phase 6 - Devcontainer Discovery and Generation

Deliver:
- standard devcontainer detection
- compatibility checks
- generated `.opencode/devcontainer.json`

Tasks:
1. detect standard devcontainer entrypoints
2. implement compatibility evaluation
3. implement extend/from-scratch branching logic
4. generate `devcontainer.json` with required baseline tooling
5. generate optional feature wiring
6. encode canonical auto-start behavior for `opencode`
7. add tests for supported detection scenarios

Acceptance criteria:
- standard devcontainer files are recognized correctly
- incompatible setups explain why they are rejected
- generated `devcontainer.json` supports the canonical launch command

## Phase 7 - Runtime Layout Generation

Deliver:
- generated `.opencode/.env`
- generated `.opencode/README.md`
- generated `.opencode/.gitignore`
- generated `.opencode/runtime_data/` structure
- native project-level `opencode` config materialization

Tasks:
1. generate root-level files in `.opencode/`
2. generate `.opencode/.env` with project-level config and runtime inputs
3. create `runtime_data/` subtree
4. write local `.gitignore` for runtime data
5. write local usage README with launch instructions and framework-doc links
6. materialize native project-level `opencode` config layout

Acceptance criteria:
- `.opencode/` matches the agreed layout
- runtime data is separated cleanly from versioned config

## Phase 8 - Mount Policy and Security Wiring

Deliver:
- RO/RW mount policy encoded in generated devcontainer config
- auth neutralization rule
- optional rootless Docker wiring

Tasks:
1. encode read-only mounts for global/framework/project config
2. encode read-write mounts for project source and `runtime_data/`
3. ensure `auth.json` is mounted read-only when present on the host
4. implement optional rootless Docker context wiring for Docker access
5. add tests for generated mount semantics

Acceptance criteria:
- generated runtime respects declared mount permissions
- auth file neutralization is always present

## Phase 9 - Final Output and End-to-End Tests

Deliver:
- final post-init output
- integration tests across the full init flow

Tasks:
1. print canonical launch command
2. print concise note that `opencode` starts automatically
3. add end-to-end tests for fresh init
4. add end-to-end tests for `--force` regeneration
5. add end-to-end tests for global settings autodetection (present vs absent)

Acceptance criteria:
- successful init ends with the exact documented launch instruction
- main project branch remains untouched by framework-specific committed artifacts

## Recommended Execution Order

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 5
6. Phase 6
7. Phase 7
8. Phase 8
9. Phase 9

## Notes for Agent-Driven Delivery

- keep each phase in a separate implementation task or PR-sized unit
- add tests in the same phase as the behavior they verify
- prefer integration fixtures for Git/worktree scenarios early
- do not expand CLI surface beyond `init` and `version` during v1 unless requirements change
