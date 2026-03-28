# Devcontainer Strategy

## Existing Devcontainer Detection

Only these standard locations are treated as existing devcontainers in v1:
- `.devcontainer/devcontainer.json`
- `.devcontainer.json`
- `.devcontainer/devcontainer.yaml`
- `.devcontainer/devcontainer.yml`

Nonstandard locations are ignored.

## Existing Devcontainer Handling

If a standard devcontainer exists:
- inspect it for compatibility with framework requirements
- if compatible, allow the user to choose extending it
- if incompatible, explain what is incompatible, advise using the `from scratch` option, and exit

The framework does not try to patch around incompatible devcontainer setups automatically.

## Generated Devcontainer Role

`.opencode/devcontainer.json` is the canonical generated runtime entrypoint.

V1 should aim to express behavior through `devcontainer.json` only.

Helper scripts are out of scope unless something later proves impossible without them.

## Default Features

Always present:
- Git inside container
- common shell utilities

## Optional Features

- DinD / Docker access
- `vi`
- `nano`
- Python + Poetry
- Node.js + npm
- Java + Maven

Feature selection is not stored separately. The generated `devcontainer.json` is the source of truth.

## DinD Rule

DinD is opt-in only.

If selected, setup must:
- check that a rootless Docker context exists
- wire the container launch to use `DOCKER_CONTEXT=rootless`

Reason:
- avoid privileged DinD as the default path
- keep security tradeoffs explicit

## Canonical Launch Command

After `init`, the framework prints:

```sh
devcontainer up --config .opencode/devcontainer.json --workspace-folder .
```

The generated devcontainer configuration should auto-start `opencode`.

Manual shell/debug alternatives are out of scope for framework UX in v1.
