# Install
```shell
git clone git@github.com:dzharikhin/codeagent-infra.git .codeagent
```
> `.codeagent` path to clone the repo in is related to `CODEAGENT_ROOT_PATH` in [.env](./.env.sample)
# Run
1. copy `[.env](./.env.sample)` into `.env` and edit if necessary
2. run
   ```shell
     HOST_UID="${UID}" GID="$(id -g)" USER="${USER}" HOST_DOCKER_GROUP_ID=$(getent group docker | cut -d':' -f3) ANTHROPIC_API_KEY=$(read -rsp "anthropic token: " p && echo $p) docker compose --verbose run --rm agent
   ```
# Extend
## Config
you can set `CUSTOM_PROJECT_CONFIG_DIR` as path to provide any project level config according to [documentation](https://opencode.ai/docs/), `CODEAGENT_ROOT_PATH` is used as a default
## Tooling
use `CUSTOM_DOCKER_IMAGE` and `CUSTOM_DOCKER_CONTEXT` to build custom image. Example: [nodejs](./node-opencode.dockerfile) 
# Warning
`auth.json` file will be created by `/connect` command with the token in plain text - try to use env variables when possible
