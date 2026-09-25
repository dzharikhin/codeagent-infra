# OpenCode Framework Configuration

This directory contains the project-level configuration for the OpenCode Framework.

## Structure

- `devcontainer.json` - DevContainer build configuration (image, features)
- `docker-compose.yaml` - Runtime configuration (env, mounts, command)
- `.env` - Runtime environment variables
- `runtime_data/` - Mutable runtime state (not versioned)

## Commands
    
### Launch

```sh
{{LAUNCH_COMMAND}}
```

### Debug

```sh
{{DEBUG_COMMAND}}
```

### Shell

```sh
{{SHELL_COMMAND}}
```

Find container name with: `docker ps | grep ocf_`

{{AGENT_MODELS_SECTION}}
## How It Works

The sandbox image is built once from `devcontainer.json` and reused across
launches; `docker-compose.yaml` wires runtime env, mounts and ports.
Agent install: {{AGENT_INSTALL_LINE}}

{{AGENT_CONFIG_LAYERS_SECTION}}
## Reconfiguring

To change the sandbox configuration (devcontainer features, port mappings):

```sh
{{RECONFIGURE_COMMAND}}
```

When run interactively, `reconfigure` offers to add or remove devcontainer features
(docker/python/nodejs/java). For Java, you can also choose
Maven and/or Gradle as build tools. The current settings are shown as defaults, so you can
toggle features on or off. Only the feature-dependent parts of `devcontainer.json` and
`docker-compose.yaml` are updated; manual customizations are preserved. In a non-interactive
context the prompt is skipped.

After the prompts it rebuilds the image, updates the cached image ID and removes the
tool's existing container (it never starts containers) — the next `launch` picks up the
new image.

Plain `launch` self-heals: when the cached image is missing (e.g. pruned by a Docker
cleanup), it rebuilds automatically. `launch --force` removes any existing container and
the cached image ID for a fully fresh session.

{{AGENT_SERVE_SECTION}}
{{AGENT_ACP_SECTION}}
## Version Control

This directory is a linked Git worktree on branch `{{BRANCH_NAME}}`.

To save configuration changes:
1. `cd {{CONFIG_DIR}}`
2. `git add . && git commit -m "Update config"`
3. `git push origin {{BRANCH_NAME}}`

The `{{CONFIG_DIR}}/` directory is a linked Git worktree. Git commands must run
from inside `{{CONFIG_DIR}}/` to affect the configuration branch.

## Documentation

- Framework docs: https://github.com/dzharikhin/codeagent-infra
{{AGENT_DOCS_LINE}}
