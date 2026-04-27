---
name: docker-service
description: Load this skill when you need to use Docker commands (docker build, docker run, docker compose, etc.) inside the container
---

## Docker-in-Docker Setup

This container supports Docker-in-Docker (DinD), but the Docker daemon is **not started automatically**.

Before running any Docker commands, you must start the Docker service:

```sh
service docker start
```

### Notes

- Wait a few seconds after starting the service before running Docker commands
- The container uses the `vfs` storage driver (not overlay2) due to lack of kernel overlayfs support in the containerized environment
- Docker data is stored in the container's writable layer and is not persisted across container restarts
- The container runs in privileged mode to support DinD
