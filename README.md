# OpenCode Framework

Framework for attaching AI coding agents to existing projects safely.

See [vision.md](vision.md) for project goals, scope, and architecture.

## Requirements

- Python 3.12+
- Git
- Docker
- devcontainer CLI (`@devcontainers/cli`)
- pipx

## Installation

The framework must be installed as an editable package from a git clone:

```sh
git clone <framework-repo-url> /path/to/opencode-framework
pipx install -e /path/to/opencode-framework
```

This is the only supported installation method. The framework repository is a required runtime asset containing templates, stub auth, and shared configuration.

## Usage

### Initialize a Project

Navigate to your project repository root and run:

```sh
ocframework init
```

This command:
- validates the environment and repository
- creates a `.opencode/` directory as a Git worktree on a separate branch
- generates devcontainer configuration
- prints launch instructions

If `.opencode/` already exists, use `--force` to back it up and regenerate:

```sh
ocframework init --force
```

The backup is created at `.opencode.backup-<timestamp>` in the project root.

### Launch the Container

```sh
ocframework launch
```

This validates the runtime context and runs `devcontainer up`.

To override the Docker context:

```sh
ocframework launch --docker-context my-context
```

By default, `DOCKER_CONTEXT=rootless` is used.

### Execute Commands in the Container

```sh
ocframework exec -- opencode debug config
ocframework exec -- bash
```

Note: `--` separates framework options from the command to run.

### Version Information

```sh
ocframework --version
ocframework
```

Both print version info, framework repo path, global config status, and auth.json status.

### Remove the Container

There is no `devcontainer down` command. To stop and remove the container:

```sh
docker rm -f $(basename "$(pwd)")
```

## Development Setup

### Install Poetry

```sh
pipx install poetry
```

### Install Dependencies

```sh
git clone <repository-url>
cd opencode-framework
poetry install
```

### Run Tests

```sh
poetry run pytest
```

### Run CLI

```sh
poetry run ocframework --version
```

### Build

```sh
poetry build
```
