# Install
```shell
git clone git@github.com:dzharikhin/codeagent-infra.git .codeagent
```
> `.codeagent` path to clone the repo in is related to `CODEAGENT_ROOT_PATH` in [.env](./.env.sample)
# Run
1. copy `[.env](./.env.sample)` into `.env` and edit if necessary
2. run
   ```shell
    HOST_UID="${UID}" GID="$(id -g)" USER="${USER}" ANTHROPIC_API_KEY=$(read -rsp "anthropic token: " p && echo $p) docker compose run --rm agent
   ```
# Extend
you can provide any project level config according to [documentation](https://opencode.ai/docs/)
# Warning
`auth.json` file will be created by `/connect` command with the token in plain text - try to use env variables when possible
