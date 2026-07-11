# OpenCode Framework

Framework for attaching AI coding agents to existing projects safely.

## TL:DR
1. `git clone <framework-repo-url> /path/to/opencode-framework`
2. `uv tool install --editable .` or `pipx install -e /path/to/opencode-framework`
3. switch to the target project
4. `ocframework init`
5. `ocframework launch`
6. profit. now you can start tweak the framework to the target project

See [vision.md](vision.md) for project goals, scope, and architecture.

## Requirements

- Python 3.12+
- Git
- Docker
- devcontainer CLI (`@devcontainers/cli`)
- pipx

## Rootless Docker Configuration

When using rootless Docker (the default `DOCKER_CONTEXT=rootless`), containers may need access to the host machine. This is required for use cases like accessing MCPs (Model Context Protocol servers) running on your host machine from IDEs or other tools.

### Configure Host Access

1. **Add to daemon.json**:
   ```json
   {
     "host-gateway-ips": ["10.0.2.2"]
   }
   ```

2. **Enable host loopback** via systemd:
   ```sh
   systemctl --user edit docker.service
   ```
   
   Add this line to the override:
   ```ini
   [Service]
   Environment="DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=false"
   ```
   
   Then reload:
   ```sh
   systemctl --user daemon-reload
   systemctl --user restart docker
   ```

This allows containers to reach the host using `host.docker.internal` or the configured gateway IP.

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

When run interactively (stdin is a TTY), `--rebuild` offers to **add or remove devcontainer features** before rebuilding. The current feature set and editor preference are shown, pre-filled as the defaults, so you can toggle docker/python/nodejs/java and the editor (vi/nano) on or off. Only the feature-dependent parts of `.opencode/devcontainer.json` and `.opencode/docker-compose.yaml` are updated; any manual customizations elsewhere are preserved.

In a non-interactive context (e.g. CI, piped stdin) the prompt is skipped and the image rebuilds with the existing configuration.

### Docker-in-Docker

If you selected the `docker` optional feature during `ocframework init`, the container includes Docker CE and runs with `privileged: true`. The image is pre-configured with the `vfs` storage driver for compatibility with sandboxed environments.

The Docker daemon **starts automatically** on container launch. The container entrypoint runs `/usr/local/share/docker-init.sh` before `opencode`, which starts dockerd with readiness checks.

Verify it's running:

```sh
docker info | grep "Storage Driver"
# Should output: Storage Driver: vfs
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
docker rm -f ocf_$(basename "$(pwd)")
```

### Run a Headless Server (Serve)

You can run the OpenCode server inside the container so that external clients
(the TUI via `opencode attach`, the SDK, IDE plugins, or the web UI) can connect
to it. This combines the `serve` subcommand with port mappings.

1. **Configure a port mapping.** During `ocframework init`, or interactively via
   `ocframework launch --rebuild`, add a mapping such as `4096:4096`. Existing
   mappings can be checked in `.opencode/docker-compose.yaml`.

2. **Launch the server**, passing `serve` (and any of its flags) through `launch`:

   ```sh
   ocframework launch -- serve --hostname 0.0.0.0 --port 4096
   ```

   The framework automatically adds `--service-ports` to `docker compose run`
   when ports are configured, exposing them to the host.

3. **Connect a client** to the mapped port, e.g.:

   ```sh
   opencode attach http://localhost:4096
   ```

Set `OPENCODE_SERVER_PASSWORD` (and optionally `OPENCODE_SERVER_USERNAME`) in
`.opencode/.env` to enable HTTP basic auth on the server.

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

### Install Dependencies

```sh
git clone <repository-url>
cd opencode-framework
poetry install
```

### Run CLI

```sh
poetry run ocframework --version
```
