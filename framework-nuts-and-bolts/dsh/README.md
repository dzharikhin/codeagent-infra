# dsh nuts and bolts

Read-only snippet library for the **dsh** (DeepSeek Harness) agent,
mounted together with `common/` into the container at
`.dsh/framework-nuts-and-bolts/`.

This directory is intentionally minimal: it exists so the read-only
compose mount resolves on a fresh init. Intended future contents mirror
the `qwen/` folder:

- `commands/` — prompt/command fragments (e.g. store-plan, init parts)
  assembled into dsh profiles.
- `mcp/` — MCP server configuration snippets for `settings.yaml`.

Nothing here is rewritten by the framework; edit the files (on the
framework side) and the next launch picks them up.
