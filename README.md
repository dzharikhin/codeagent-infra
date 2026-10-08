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

> **Roadmap:** the agent tool is becoming configurable (`opencode` | `qwen` |
> `dsh`) as part of a 3-part restructure (sandbox / agent integration /
> nuts-and-bolts). Design and implementation plan:
> [tool-adoption.md](tool-adoption.md); third-tool plan:
> [dsh.md](dsh.md).

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

### Multiple Agents in One Project

Every tool initializes independently, so a project can host several harnesses
side by side — each with its own config directory, `.env`, container, volumes,
and image tag. To add a second agent next to an existing one:

```sh
ocframework init --tool qwen
```

Existing harnesses are never touched. `ocframework launch` then starts the
single configured agent automatically, or asks which one to launch when
several are configured (pass `--tool <name>` to choose explicitly, e.g. in
scripts).

### Environment Configuration

The `init` command generates `.opencode/.env` with placeholder values. Edit this file to configure environment variables for your project.

You can also use a global environment file at `~/.config/opencode/.env` for opencode projects (on Unix-like systems) or `%APPDATA%\opencode\.env` on Windows; qwen projects use `~/.qwen/.env`, dsh projects use `~/.dsh/.env`. This file is automatically loaded if present, with the lowest priority.

At launch time, you can override environment variables:

```sh
# Use a different environment file
ocframework launch --env-file prod.env

# Override individual variables (can be used multiple times)
ocframework launch -e API_KEY=secret123 -e DEBUG=true
```

Environment precedence (lowest to highest):
1. Global env file (`~/.config/opencode/.env` for opencode, `~/.qwen/.env` for qwen, `~/.dsh/.env` for dsh; auto-loaded)
2. Base `.opencode/.env` file
3. Override file (`--env-file`)
4. Command-line variables (`-e KEY=VALUE`)

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

To reconfigure the sandbox (e.g., change devcontainer features or port mappings):

```sh
ocframework reconfigure
```

When run interactively (stdin is a TTY), `reconfigure` offers to **add or remove devcontainer features** before rebuilding. The current feature set and editor preference are shown, pre-filled as the defaults, so you can toggle docker/python/nodejs/java/ssh and the editor (vi/nano) on or off. Only the feature-dependent parts of `.opencode/devcontainer.json` and `.opencode/docker-compose.yaml` are updated; any manual customizations elsewhere are preserved.

On every run — interactive or not — `reconfigure` also re-renders the Dockerfile-generating `initializeCommand` in `devcontainer.json` from the current framework code (migrating legacy feature keys such as `docker-in-docker:2` to the podman engine along the way), so image-level fixes propagate to the rebuilt image without a re-init.

After the prompts it rebuilds the image, updates the cached image ID and removes the tool's existing container (it never starts containers) — the next `ocframework launch` picks up the new image.

In a non-interactive context (e.g. CI, piped stdin) the prompts are skipped and the detected configuration is kept, but the reconciliation still runs (Dockerfile content, compose, `.env`) before the rebuild.

`launch` self-heals: when the cached image is missing (e.g. pruned by a Docker cleanup), it rebuilds automatically on the next launch. `launch --force` removes any existing container and the cached image ID for a fully fresh session.

### Docker Support (podman engine, two modes)

If you selected the `docker` optional feature during `ocframework init`, the container includes a Docker-compatible CLI backed by **podman** — never `privileged: true`. Everything works through the familiar `docker` CLI: a wrapper transparently forwards `docker run/build/compose` to the podman engine. No daemon startup is needed — there is no dockerd; podman runs daemonless.

The framework picks the mode automatically from your Docker daemon at `init`/`reconfigure` time and prints it, e.g.:

```
Docker daemon: rootless → caps mode (SYS_ADMIN, NET_ADMIN), REMOTE_USER=root
Docker daemon: rootful → standard mode (no caps), REMOTE_USER=vscode
```

- **Rootless daemon → caps mode.** The agent runs as `root` inside the sandbox (which is how container root maps to your host user — files you create are owned by you). The inner podman engine runs rootful with exactly two extra capabilities, `SYS_ADMIN` and `NET_ADMIN` — far narrower than `privileged` (no host devices, no module loading), and both remain confined by the outer rootless user namespace, so they never reach host root.
- **Rootful daemon → standard mode.** The agent runs as the unprivileged `vscode` account and podman runs rootless — no capabilities at all. (Assumes your host user id is 1000, which maps to `vscode`; on hosts with a different uid prefer a rootless daemon, where container root maps to any host uid.)

If `launch` detects a mismatch — e.g. you switched your Docker daemon between rootless and rootful after generating the harness — it fails with a clear error and two remedies: point launch at a matching daemon (`docker context use <context>` or `ocframework launch --docker-context <context>`) or regenerate the harness with `ocframework reconfigure`. After switching daemons, podman may report `database graph driver mismatch` once — remove the stale storage volume (`docker volume rm docker-<repo>-<tool>`) and relaunch.

Inner containers run with cgroups disabled (the framework bakes this into the image): the sandbox's cgroup filesystem is read-only, so cgroup-based resource limits aren't available for containers started inside — plain `docker run` works without any flags.

Verify it works:

```sh
docker info | grep -E "rootless|Storage Driver"
# in standard mode rootless is expected; storage is overlay (or fuse-overlay in nested sandboxes)
```

A named volume `docker-<repo>-<tool>` is mounted at the podman storage root (`/home/vscode/.local/share/containers` in standard mode, `/var/lib/containers` in caps mode) to persist images across container restarts.

### Host Identity (git config, SSH keys)

Your host `~/.gitconfig` is mirrored read-only into the container at `/home/$REMOTE_USER/.gitconfig` — always on, refreshed by `reconfigure`. This propagates your commit identity (`user.name`/`user.email`), aliases, `insteadOf` URL rewrites and `safe.directory` entries. Host-only settings that cannot work inside the sandbox (GPG signing without keys, credential helpers referencing host binaries, absolute `[include]` paths) fail loudly rather than being sanitized.

The optional `ssh` feature (selectable at `init`, toggleable at `reconfigure`) additionally mirrors your host `~/.ssh` directory (keys, `config`, `known_hosts`) read-only, enabling git push/pull over SSH remotes from inside the sandbox. Everything under `~/.ssh` — including private key material — becomes readable by the agent in the container; `:ro` prevents modification, not reads. Caveats: `known_hosts` cannot grow from inside, `ControlMaster` sockets cannot be created, and passphrase-protected keys cannot be unlocked non-interactively.

### Debug Configuration

```sh
ocframework launch -- debug config
```

### Shell Access

```sh
docker exec -it <container_name> /bin/bash
```

Find container name with: `docker ps | grep ocf-`

### List Available Models

With model autodiscovery enabled (via the `opencode-models-discovery` plugin),
list every available model — including autodiscovered ones — with:

```sh
opencode models
```

Optionally filter by provider or show metadata:

```sh
opencode models <provider>
opencode models <provider> --verbose
```

### Version Information

```sh
ocframework --version
ocframework
```

Both print version info, framework repo path, and the global config/auth
status for every supported tool: opencode config dir + `auth.json`, qwen
`~/.qwen/settings.json`, dsh `~/.dsh/settings.yaml` + `~/.dsh/.credentials.yaml`
(found/path, or expected path when missing).

### Remove the Container

There is no `devcontainer down` command. To stop and remove the container
(named `ocf_<repo>_<tool>`, e.g. `ocf_myrepo_qwen`):

```sh
docker rm -f ocf_$(basename "$(pwd)")_<tool>
```

### Run a Headless Server (Serve)

You can run the OpenCode server inside the container so that external clients
(the TUI via `opencode attach`, the SDK, IDE plugins, or the web UI) can connect
to it. This combines the `serve` subcommand with port mappings.

1. **Configure a port mapping.** During `ocframework init`, or interactively via
   `ocframework reconfigure`, add a mapping such as `4096:4096`. Existing
   mappings can be checked in `.opencode/docker-compose.yaml`.

2. **Launch the server**, passing `serve` (and any of its flags) through `launch`:

   ```sh
   ocframework launch -- serve --hostname 0.0.0.0 --port 4096
   ```

   The framework automatically adds `--service-ports` to `docker compose run`
   when ports are configured, exposing them to the host. When `--server` is
   used, each configured port is published individually (equivalent to
   `--service-ports`) alongside the server port, because `--service-ports` and
   `--publish` are mutually exclusive in `docker compose run`.

3. **Connect a client** to the mapped port, e.g.:

   ```sh
   opencode attach http://localhost:4096
   ```

Set `OPENCODE_SERVER_PASSWORD` (and optionally `OPENCODE_SERVER_USERNAME`) in
`.opencode/.env` to enable HTTP basic auth on the server.

The `--server` shorthand wraps the per-tool serve command and publishes the
tool's container port (opencode 4096, qwen Web Shell 4170, dsh Web UI 3080).
For qwen the framework auto-generates a `QWEN_SERVER_TOKEN` when none is set.
For dsh there is no TUI and no framework-managed token: it prints a one-time
`?token=…` URL at startup that you copy into the browser, and plain
`ocframework launch --tool dsh` (without `--server`) exits with a usage error
by design. See the generated `<config-dir>/README.md` for the exact commands.

### Connect an Editor (ACP)

`ocframework launch --acp <postfix>` runs the sandboxed agent in ACP (Agent
Client Protocol) mode: the editor speaks JSON-RPC to the agent over stdio, while the
container, mounts, env layers and ports stay exactly as in a normal launch.
Supported for opencode and qwen; dsh has no stdio mode (use `--server` and the
Web UI instead).

```sh
ocframework launch --tool opencode --acp zed
```

The postfix is required and becomes part of the container name
(`ocf_<repo>_<tool>_<postfix>`), so concurrent ACP sessions on one repository
never collide. Managed volumes (including the Docker-in-Docker data volume)
get the same postfix, so every session owns its state — a reused postfix
replaces the session and keeps its warm caches, a new postfix starts fully
isolated. An existing container with the same name is removed first.
Launch chatter (image reuse, port
notes, warnings) is redirected to stderr so stdout carries only the protocol
stream. In Zed, register the launch command as a custom agent:

```json
{
  "agent": {
    "custom": {
      "command": "ocframework",
      "args": ["launch", "--tool", "opencode", "--acp", "zed"],
      "type": "custom"
    }
  }
}
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
