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

Find container name with: `docker ps | grep ocf-`

## How It Works

## Rebuilding

To rebuild the image (e.g., after changing features):

```sh
{{LAUNCH_COMMAND}} --rebuild
```

When run interactively, `--rebuild` first offers to add or remove devcontainer features
(docker/python/nodejs/java) and change the editor preference. The current settings are
shown as defaults, so you can toggle features on or off. Only the feature-dependent parts
of `devcontainer.json` and `docker-compose.yaml` are updated; manual customizations are
preserved. In a non-interactive context the prompt is skipped.

## Version Control

This directory is a linked Git worktree on branch `{{BRANCH_NAME}}`.

To save configuration changes:
1. `cd .opencode`
2. `git add . && git commit -m "Update config"`
3. `git push origin {{BRANCH_NAME}}`

The `.opencode/` directory is a linked Git worktree. Git commands must run
from inside `.opencode/` to affect the configuration branch.

## Documentation

- Framework docs: https://github.com/dzharikhin/codeagent-infra
- OpenCode docs: https://opencode.ai
