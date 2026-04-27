---
name: docker-service
description: Load this skill when you need to use Docker commands (docker build, docker run, docker compose, etc.) inside the container
---

## Docker-in-Docker Setup

This container supports Docker-in-Docker (DinD), but the Docker daemon is **not started automatically**.

Before running any Docker commands, you must start the Docker daemon (systemd is not available in this container):

```sh
/usr/local/share/docker-init.sh &
```

This script is installed by the `docker-in-docker:2` devcontainer feature and handles:
- Cleaning stale PID files from unclean shutdowns
- Enabling cgroup v2 nesting
- Starting `dockerd` with retry logic (up to 5 attempts)
- Polling `docker info` to confirm readiness before returning

### Notes

- The script blocks until Docker is ready, so no manual wait is needed
- The container uses the `vfs` storage driver (not overlay2) due to lack of kernel overlayfs support in the containerized environment
- Docker data is stored in the container's writable layer and is not persisted across container restarts
- The container runs in privileged mode to support DinD
