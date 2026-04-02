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

### Environment Configuration

The `init` command generates `.opencode/.env` with placeholder values. Edit this file to configure environment variables for your project.

At launch time, you can override environment variables:

```sh
# Use a different environment file
ocframework launch --env-file prod.env

# Override individual variables (can be used multiple times)
ocframework launch -e API_KEY=secret123 -e DEBUG=true
```

Environment precedence (lowest to highest):
1. Base `.opencode/.env` file
2. Override file (`--env-file`)
3. Command-line variables (`-e KEY=VALUE`)

The framework supports variable interpolation in `.env` files: `$VAR`, `${VAR}`, and `${VAR:-default}` syntax.

### Launch the Container

```sh
ocframework launch
```

This validates the runtime context, builds the devcontainer image (if needed), and runs OpenCode using docker compose.

To override the Docker context:

```sh
ocframework launch --docker-context my-context
```

By default, `DOCKER_CONTEXT=rootless` is used.

To rebuild the image (e.g., after changing devcontainer features):

```sh
ocframework launch --rebuild
```

### Debug Configuration

```sh
ocframework launch -- debug config
```

### Shell Access

```sh
docker exec -it <container_name> /bin/bash
```

Find container name with: `docker ps | grep ocf-`

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

## Architecture

### DevContainer + Docker Compose

The framework uses a hybrid approach:

1. **DevContainer** builds the container image with features, tooling, and base configuration
2. **Docker Compose** runs the container with runtime configuration (environment, mounts, commands)

**Why not pure DevContainer?**

The DevContainer CLI (`devcontainer up`) lacks the ability to propagate arbitrary environment variables from the host to the container at runtime. It only supports a fixed set of predefined variables and doesn't allow dynamic injection of environment configuration.

By using devcontainer for image building and docker compose for runtime, we get:

- Rich devcontainer features for image construction (features, lifecycle scripts)
- Flexible environment injection via `docker compose run --env`
- Full control over mounts and runtime configuration

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
