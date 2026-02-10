# Install
`git submodule add git@github.com:dzharikhin/codeagent-infra.git .codeagent`
# Run
`HOST_UID="${UID}" GID="$(id -g)" USER="${USER}" docker compose run --rm agent`
# Extend
- create `agents` folder and fill [agents](https://opencode.ai/docs/agents/#markdown)