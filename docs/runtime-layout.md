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

The following XDG-backed directories are created:
- `.cache/` - XDG cache directory
- `.local/share/` - XDG data directory  
- `.local/state/` - XDG state directory

These directories are mounted into the devcontainer and persist across container rebuilds.

## Runtime Env File

File name:
- `.opencode/.env`

Semantics:
- project-level runtime and configuration inputs
- no setup metadata

Examples of intended contents:
- `OPENCODE_VERSION` — opencode version to use (passed to devcontainer feature)
- provider base URL overrides for standard providers
- `DEFAULT_MODEL`
- `SMALL_MODEL`
- `EDITOR`
- notification command

Values that are directly represented in `devcontainer.json` features or settings should not be duplicated unless they are intended as environment inputs for generation or runtime behavior.

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
