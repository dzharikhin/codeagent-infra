# Proposed Tech Stack

## Primary Stack

- `Python 3.12+` - implementation language for the framework CLI
- `pipx` - installation and distribution of the CLI tool
- `git` - repository validation, orphan-branch creation, and linked worktree management
- `Docker` - isolation boundary for the agent runtime
- `devcontainer-cli` - standard way to build and run the configured environment
- `opencode` - coding agent engine

## Python-Level Libraries

- `Typer` - CLI commands and interactive setup wizard
- `pydantic` - validation of generation inputs and internal models
- `Jinja2` or plain Python rendering - generation of `devcontainer.json`, `.env`, and `README.md`
- Python standard library:
  - `pathlib`
  - `subprocess`
  - `shutil`
  - `json`
  - `datetime`

## Generated Artifact Formats

- JSON for `devcontainer.json`
- `.env` for project-level runtime and configuration inputs
- Markdown for generated local usage documentation
- native `opencode` project config layout in `.opencode/`

## Test Stack

- `pytest` - unit and integration-style tests
- fixture repos for Git/worktree scenarios
- subprocess-driven tests for CLI preflight and generation flows

## Intentional Omissions

- no database
- no background service or daemon
- no framework-specific launch service
- no custom config precedence engine
