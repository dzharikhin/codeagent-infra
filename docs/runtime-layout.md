# Runtime Layout

## `.opencode/` Root

The `.opencode/` directory is both:
- the project-level `opencode` config root
- the per-developer framework worktree root

Extra files and directories are allowed there.

## Root-Level Contents

- native `opencode` project config in the layout expected by `opencode`
- `devcontainer.json`
- `.env`
- `README.md`
- `.gitignore`

## Runtime Data

All mutable runtime state lives under:
- `.opencode/runtime_data/`

V1 supports all of the following categories there:
- logs
- caches
- downloaded tools and dependencies
- temporary files
- agent session/history data
- scratch/output data
- persisted home fragments
- custom runtime directories

## Runtime Env File

File name:
- `.opencode/.env`

Semantics:
- runtime overrides only
- no setup metadata

Examples of intended contents:
- `EDITOR`
- provider base URL overrides
- `DEFAULT_MODEL`
- `SMALL_MODEL`
- notification command

Wizard selections that are already visible in `devcontainer.json` should not be duplicated here.

## Persisted Home Policy

Fixed persisted base:
- `~/.config/opencode`
- `~/.local`
- `~/.cache`
- `~/.bun`

Feature-based persisted additions:
- editor-specific state
- Python/Poetry state
- Node/npm state
- Java/Maven state
- other selected tool state

Not persisted:
- generic temp under home
- arbitrary custom extra home paths

## Versioned vs Local Data

Versioned in the config worktree:
- project-level config
- generated runtime wiring files
- local usage documentation

Not intended for versioning:
- mutable data under `.opencode/runtime_data/`
