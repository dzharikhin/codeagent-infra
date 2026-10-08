"""Devcontainer file generation and feature reconciliation."""

import json
from typing import List, Optional

from opencode_framework.agent.registry import DEFAULT_TOOL, ToolSpec, get_tool_spec
from opencode_framework.generators.base import FileGenerator, GenerationContext
from opencode_framework.generators.templates import TemplateHandler


class DevcontainerGenerator(FileGenerator):
    """Generates devcontainer.json in the tool's config directory."""

    PLACEHOLDER_DOCKERFILE_INITIALIZER = "{{DOCKERFILE_INITIALIZER}}"

    APT_PACKAGES_FEATURE_URL = "ghcr.io/devcontainers-extra/features/apt-packages:1"
    LEGACY_DIND_FEATURE_URL = "ghcr.io/devcontainers/features/docker-in-docker:2"

    # Podman ships as plain apt packages merged into the base apt-packages
    # feature (the one that also installs ripgrep). podman-docker provides
    # the /usr/bin/docker shim; podman-compose (1.0.6) is the distro-paired
    # compose provider for podman 4.9; fuse-overlayfs is the graph driver
    # for rootless containers; uidmap provides newuidmap/newgidmap for user
    # namespace id mapping; slirp4netns/passt handles rootless networking.
    # nftables ships the nft binary netavark executes for its default
    # nftables firewall backend — not a hard podman dependency, and
    # without it every default-network run dies with `netavark: nftables
    # error: unable to execute "nft"` (observed on the resolute base
    # image; the hello-world acceptance check).
    PODMAN_PACKAGES = (
        "podman,podman-docker,podman-compose,fuse-overlayfs,"
        "fuse3,uidmap,slirp4netns,passt,nftables"
    )

    # The ssh feature's devcontainer footprint: openssh-client merged
    # into the base apt-packages feature (docker/PODMAN_PACKAGES
    # pattern). The package guarantees the ssh binary in the image and
    # doubles as the detection marker in detect().
    SSH_APT_PACKAGE = "openssh-client"

    # Dockerfile slot rendered when the podman feature is enabled.
    # Everything podman needs besides these lines is either a package
    # (PODMAN_PACKAGES above) or auto-detected at runtime (verified with
    # podman 4.9 / Ubuntu 24.04 inside a docker-default container; the
    # base image default is now resolute, whose apt resolves podman 5.x —
    # same containers.conf contract, smoke-test after distro jumps):
    # cgroupfs manager and file events logger fall back automatically
    # without systemd/journald, and `podman compose` finds a compose
    # provider on PATH. One minimal /etc/containers/containers.conf IS
    # baked anyway: the sandbox mounts /sys/fs/cgroup read-only, so
    # cgroup creation must be disabled outright — the cgroupfs fallback
    # alone still tries to create /libpod_parent and crun dies with
    # `cgroup.subtree_control: Read-only file system` (validated
    # manually: `docker run hello-world` fails without the key, works
    # with `--cgroups=disabled`). `cgroups` must sit in the
    # [containers] table, NOT [engine] (it is a containers.conf
    # [containers]-table key; misplaced, podman never applies it).
    # cgroup_manager and events_logger are pinned alongside so behavior
    # no longer depends on the silent fallbacks; the storage driver
    # stays auto-detected (overlay / fuse-overlayfs).
    # Subuid/subgid ranges are assumed to be pre-allocated by user
    # creation (stock login.defs makes useradd assign 100000:65536).
    #   - nodocker sentinel: the shim checks it at runtime, but the
    #     devcontainer CLI runs template stages before feature packages
    #     install, so `mkdir -p` guards against /etc/containers being
    #     absent until containers-common ships it
    #   - /usr/local/bin/docker wrapper shadowing podman-docker's
    #     /usr/bin/docker: podman itself has no "run as another user"
    #     override (its rootful vs rootless path is decided by euid),
    #     so a root agent is dropped to the vscode service account
    #     (runuser: HOME switches to /home/vscode, other env vars such
    #     as BUILDAH_ISOLATION survive) to keep podman on its validated
    #     rootless path; non-root agents exec podman directly. The four
    #     XDG base-directory vars are unset between runuser and podman:
    #     the agent env pins them to /home/${REMOTE_USER}/... (root by
    #     default), which would redirect podman's rootless graph root
    #     away from the pinned volume; unset, podman falls back to
    #     HOME-based defaults under /home/vscode. The vscode account is
    #     assumed to exist already (created by the common-utils feature
    #     on default harnesses, or by the base image); the wrapper fails
    #     loudly if it does not. The build-time `command -v` assertion
    #     fails the build if PATH resolution ever stops preferring
    #     /usr/local/bin/docker over /usr/bin/docker. Consequence: the
    #     docker graph-root named volume must be pinned to
    #     /home/vscode/.local/share/containers (see
    #     PODMAN_GRAPH_ROOT_TARGET in generators/templates.py)
    #     regardless of REMOTE_USER, and that directory is baked
    #     vscode-owned into the image so a fresh named volume's copy-up
    #     inherits the ownership (an empty root-owned volume would leave
    #     rootless podman unable to write its graph root).
    #   - BUILDAH_ISOLATION=chroot for `docker build` inside the
    #     container (default `oci` spawns a nested runtime which fails
    #     under the sandbox's default seccomp profile)
    PODMAN_DOCKERFILE_BLOCK = (
        "RUN mkdir -p /etc/containers && touch /etc/containers/nodocker\n"
        "RUN printf '%s\\n' \\\n"
        "      '[containers]' \\\n"
        "      'cgroups = \"disabled\"' \\\n"
        "      '' \\\n"
        "      '[engine]' \\\n"
        "      'cgroup_manager = \"cgroupfs\"' \\\n"
        "      'events_logger = \"file\"' \\\n"
        "      > /etc/containers/containers.conf && \\\n"
        "    grep -q 'cgroups = \"disabled\"' /etc/containers/containers.conf\n"
        "RUN mkdir -p /home/vscode/.local/share/containers && \\\n"
        "    chown vscode:vscode /home/vscode/.local/share/containers\n"
        "RUN printf '%s\\n' \\\n"
        "      '#!/bin/sh' \\\n"
        '      \'[ "$(id -u)" = "0" ] && exec runuser -u vscode --'
        " /usr/bin/env -u XDG_DATA_HOME -u XDG_CONFIG_HOME"
        ' -u XDG_STATE_HOME -u XDG_CACHE_HOME /usr/bin/podman "$@"\' \\\n'
        "      'exec /usr/bin/podman \"$@\"'"
        " > /usr/local/bin/docker && \\\n"
        "    chmod +x /usr/local/bin/docker && \\\n"
        "    command -v docker | grep -q '^/usr/local/bin/docker$'\n"
        "ENV BUILDAH_ISOLATION=chroot"
    )

    # Dockerfile slot rendered when the podman feature is enabled AND the
    # outer Docker daemon was detected as rootless (caps mode). Selected by
    # GenerationContext.podman_caps, which init/reconfigure derive from
    # detect_daemon_rootless (sandbox/runtime.py).
    #
    # Why caps mode exists: on rootless outer daemons, the standard mode's
    # rootless-podman-inside path is structurally broken under rootlesskit
    # nesting — multi-line uid_map needs setuid newuidmap, which is EPERM
    # at userns depth 1 (`newuidmap: write to uid_map failed: EPERM`;
    # single-line `unshare -Ur` works, so only the helper path is broken).
    # It also violates the uid-consistency invariant: on rootless outer
    # daemons only container root maps to the host developer, so the agent
    # must run as root (REMOTE_USER=root) for project files to stay
    # access-consistent between sandbox and host.
    #
    # The engine therefore follows the agent: rootful podman where the
    # agent is root. Rootful podman needs two capabilities, both honored
    # by rootless outer daemons (probed: CapEff 0xa80425fb → 0xa82435fb):
    #   - CAP_SYS_ADMIN: lets crun mount /proc at userns depth 1 (depth-2
    #     fresh unshare is kernel-denied; depth-1 works)
    #   - CAP_NET_ADMIN: sets up bridge networking; the remaining blocker
    #     was the read-only /proc/sys inherited from the outer rootless
    #     daemon's proc mount (`crun: open /proc/sys/net/ipv4/
    #     ping_group_range: Read-only file system`), which the root branch
    #     fixes with a tolerant `mount -o remount,rw /proc/sys` (remount
    #     is permitted at depth 1 with CAP_SYS_ADMIN; failure tolerated
    #     so non-bridge commands never break on it)
    # Both caps stay scoped by the rootlesskit userns — never host root;
    # caps mode is strictly narrower than `privileged: true` (2 caps vs
    # 41, no host device tree, no module loading).
    #
    # Differences vs the standard block:
    #   - no `runuser`, no XDG unsetting, no vscode anywhere: the root
    #     agent execs podman directly on its rootful path; a non-root
    #     agent (defensive branch) gets plain rootless podman
    #   - /etc/containers/containers.conf IS baked (rootful podman in the
    #     sandbox needs the probed fallbacks: cgroupfs manager, file
    #     events logger, cgroups disabled — none auto-detectable without
    #     systemd/journald). The storage driver stays auto-detected:
    #     rootful podman mounts real overlay (docker info inside the
    #     sandbox showed graphDriverName: overlay while the vfs pin was
    #     present — [storage] is not a containers.conf table, driver
    #     config lives in storage.conf — so the pin was a silent no-op
    #     and is dropped). `cgroups` is a
    #     [containers]-table key, NOT [engine]: misplaced under [engine],
    #     podman never applies it and every run dies on the sandbox's
    #     read-only /sys/fs/cgroup (`crun: ... cgroup.subtree_control:
    #     Read-only file system`; validated manually — `docker run
    #     hello-world` needs exactly this key to work flagless). The
    #     conf RUN only asserts the conf bake; the `command -v docker`
    #     PATH assertion lives in the wrapper RUN below it because the
    #     wrapper must exist before `command -v docker` can resolve to it
    #   - no graph-root ownership bake: the rootful graph root defaults
    #     to /var/lib/containers and root writes it freely (see
    #     PODMAN_CAPS_GRAPH_ROOT_TARGET in generators/templates.py)
    #   - BUILDAH_ISOLATION=chroot kept: proven and avoids the nested-OCI
    #     runtime fragility under the sandbox's seccomp profile
    PODMAN_CAPS_DOCKERFILE_BLOCK = (
        "RUN mkdir -p /etc/containers && touch /etc/containers/nodocker\n"
        "RUN printf '%s\\n' \\\n"
        "      '[containers]' \\\n"
        "      'cgroups = \"disabled\"' \\\n"
        "      '' \\\n"
        "      '[engine]' \\\n"
        "      'cgroup_manager = \"cgroupfs\"' \\\n"
        "      'events_logger = \"file\"' \\\n"
        "      > /etc/containers/containers.conf && \\\n"
        "    grep -q 'cgroups = \"disabled\"' /etc/containers/containers.conf\n"
        "RUN printf '%s\\n' \\\n"
        "      '#!/bin/sh' \\\n"
        '      \'[ "$(id -u)" = "0" ] && {'
        " mount -o remount,rw /proc/sys 2>/dev/null || true;"
        ' exec /usr/bin/podman "$@"; }\' \\\n'
        "      'exec /usr/bin/podman \"$@\"'"
        " > /usr/local/bin/docker && \\\n"
        "    chmod +x /usr/local/bin/docker && \\\n"
        "    command -v docker | grep -q '^/usr/local/bin/docker$'\n"
        "ENV BUILDAH_ISOLATION=chroot"
    )

    FEATURE_URL_MAP: dict = {
        "python": "ghcr.io/devcontainers/features/python:1",
        "nodejs": "ghcr.io/devcontainers/features/node:1",
        "java": "ghcr.io/devcontainers/features/java:1",
    }

    _JAVA_BUILD_TOOL_PARAM = {"maven": "installMaven", "gradle": "installGradle"}

    _FEATURE_DEFAULTS: dict = {
        "python": {
            "version": "${localEnv:PYTHON_VERSION:3.14}",
            "toolsToInstall": "uv,poetry,virtualenv,pipenv,black,pytest",
        },
        "nodejs": {
            "version": "${localEnv:NODE_VERSION:lts}",
        },
        "java": {
            "version": "${localEnv:JAVA_VERSION:25}",
        },
    }

    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer configuration (build-only)."""
        devcontainer = self._generate_scratch(ctx)

        dc_path = ctx.config_dir / "devcontainer.json"
        dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")

    @staticmethod
    def _load_template() -> dict:
        """Load devcontainer template from package resources."""
        return TemplateHandler.load_devcontainer_template()

    @staticmethod
    def _build_install_block(spec: ToolSpec) -> str:
        """Build the Dockerfile install block for a tool spec.

        ARG declarations for the spec's build args followed by the
        install snippet; empty when the tool installs via a
        devcontainer feature instead.

        Args:
            spec: Tool spec providing build args and install snippet

        Returns:
            Install block lines, or "" for feature-installed tools
        """
        lines: List[str] = [f"ARG {arg}=latest" for arg in spec.install.build_args]
        if spec.install.dockerfile_snippet:
            lines.append(spec.install.dockerfile_snippet)
        return "\n".join(lines)

    @staticmethod
    def _build_dockerfile_initializer(
        agent_tool: str = DEFAULT_TOOL,
        optional_features: Optional[List[str]] = None,
        podman_caps: bool = False,
    ) -> str:
        """Build the initializeCommand for Dockerfile generation.

        Loads the dockerfile template, injects the tool's install block
        into the {{AGENT_INSTALL}} slot and the podman engine setup into
        the {{PODMAN_SUPPORT}} slot, and wraps the content in a quoted
        heredoc that writes the Dockerfile into the tool's config
        directory (workspace-relative at initializeCommand runtime).
        The quoted delimiter keeps the content byte-for-byte verbatim —
        no shell expansion and no backslash-sequence interpretation.

        Args:
            agent_tool: Agent tool name ("opencode" | "qwen" | "dsh")
            optional_features: Enabled optional features; the docker
                feature renders the podman Dockerfile block, others drop
                the slot line
            podman_caps: Caps-mode selector for the docker feature —
                True renders PODMAN_CAPS_DOCKERFILE_BLOCK (rootful
                podman for a root agent, for rootless outer daemons),
                False renders the standard PODMAN_DOCKERFILE_BLOCK
                (rootless podman via the vscode delegation wrapper)

        Returns:
            Shell command string for initializeCommand
        """
        spec = get_tool_spec(agent_tool)
        dockerfile_content = TemplateHandler.load_dockerfile_template()
        install_block = DevcontainerGenerator._build_install_block(spec)
        if install_block:
            dockerfile_content = dockerfile_content.replace(
                "{{AGENT_INSTALL}}", install_block
            )
        else:
            dockerfile_content = dockerfile_content.replace("\n{{AGENT_INSTALL}}", "")
        if optional_features and "docker" in optional_features:
            podman_block = (
                DevcontainerGenerator.PODMAN_CAPS_DOCKERFILE_BLOCK
                if podman_caps
                else DevcontainerGenerator.PODMAN_DOCKERFILE_BLOCK
            )
            dockerfile_content = dockerfile_content.replace(
                "{{PODMAN_SUPPORT}}\n",
                podman_block + "\n",
            )
        else:
            dockerfile_content = dockerfile_content.replace("{{PODMAN_SUPPORT}}\n", "")
        return (
            f"cat > {spec.config_dirname}/runtime_data/Dockerfile"
            f" <<'OCF_DOCKERFILE_EOF'\n"
            f"{dockerfile_content}"
            "OCF_DOCKERFILE_EOF"
        )

    @staticmethod
    def _reconcile_java_build_tools(
        features: dict, java_build_tools: List[str]
    ) -> None:
        """Set installMaven and installGradle flags on the Java feature.

        Args:
            features: The features dict (mutated in place)
            java_build_tools: List of enabled tools (e.g. ["maven"],
                ["gradle"], ["maven", "gradle"])
        """
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        if java_url not in features:
            return

        maven_installed = "maven" in java_build_tools
        gradle_installed = "gradle" in java_build_tools

        features[java_url]["installMaven"] = maven_installed
        features[java_url]["installGradle"] = gradle_installed

    def _generate_scratch(self, ctx: GenerationContext) -> dict:
        """Generate devcontainer config from template (build-only)."""
        template = DevcontainerGenerator._load_template()
        spec = get_tool_spec(ctx.agent_tool)

        features = dict(template.get("features", {}))
        devcontainer = dict(template)
        self._add_agent_install(devcontainer, features, spec)
        self._add_optional_features(
            features,
            ctx.optional_features,
            java_build_tools=ctx.java_build_tools,
        )

        devcontainer["features"] = features

        if self.PLACEHOLDER_DOCKERFILE_INITIALIZER in devcontainer.get(
            "initializeCommand", ""
        ):
            devcontainer["initializeCommand"] = self._build_dockerfile_initializer(
                ctx.agent_tool, ctx.optional_features, ctx.podman_caps
            )

        return devcontainer

    @staticmethod
    def _add_agent_install(devcontainer: dict, features: dict, spec: ToolSpec) -> None:
        """Fill the agent install slots in the devcontainer config.

        Feature-installed tools get their devcontainer feature entry with
        a localEnv version pin; Dockerfile-installed tools get their
        build args on the build section instead.

        Args:
            devcontainer: Devcontainer config dict (mutated for build args)
            features: Features dict (mutated for feature-installed tools)
            spec: Tool spec providing the install mechanism
        """
        install = spec.install
        if install.devcontainer_feature:
            version_env = install.feature_version_env or "OCF_AGENT_VERSION"
            features[install.devcontainer_feature] = {
                "version": f"${{localEnv:{version_env}:latest}}"
            }
        if install.build_args:
            build = devcontainer.setdefault("build", {})
            build["args"] = {
                arg: f"${{localEnv:{arg}:latest}}" for arg in install.build_args
            }

    @staticmethod
    def _merge_apt_packages(features: dict, packages_to_add: List[str]) -> None:
        """Merge packages into the base apt-packages feature entry.

        Preserves the packages already listed (e.g. ripgrep); creates
        the entry when absent.

        Args:
            features: The features dict (mutated in place)
            packages_to_add: apt package names to merge in
        """
        entry = features.setdefault(DevcontainerGenerator.APT_PACKAGES_FEATURE_URL, {})
        packages = [
            p.strip() for p in str(entry.get("packages", "")).split(",") if p.strip()
        ]
        for pkg in packages_to_add:
            if pkg not in packages:
                packages.append(pkg)
        entry["packages"] = ",".join(packages)

    @staticmethod
    def _filter_apt_packages(features: dict, packages_to_remove: List[str]) -> None:
        """Filter packages out of the base apt-packages feature entry.

        Keeps unrelated packages (ripgrep); a no-op when the entry is
        absent.

        Args:
            features: The features dict (mutated in place)
            packages_to_remove: apt package names to drop
        """
        entry = features.get(DevcontainerGenerator.APT_PACKAGES_FEATURE_URL)
        if not isinstance(entry, dict):
            return
        packages = [
            p.strip() for p in str(entry.get("packages", "")).split(",") if p.strip()
        ]
        remove = set(packages_to_remove)
        entry["packages"] = ",".join(p for p in packages if p not in remove)

    @staticmethod
    def _add_one_feature(features: dict, key: str) -> None:
        """Add a single optional feature by its key.

        The docker and ssh features have no devcontainer feature URL of
        their own; their apt packages are merged into the base
        apt-packages feature (preserving the packages already listed,
        e.g. ripgrep).
        """
        if key == "docker":
            DevcontainerGenerator._merge_apt_packages(
                features, DevcontainerGenerator.PODMAN_PACKAGES.split(",")
            )
            return
        if key == "ssh":
            DevcontainerGenerator._merge_apt_packages(
                features, [DevcontainerGenerator.SSH_APT_PACKAGE]
            )
            return
        url = DevcontainerGenerator.FEATURE_URL_MAP.get(key)
        if url is not None:
            features[url] = dict(DevcontainerGenerator._FEATURE_DEFAULTS[key])

    @staticmethod
    def _remove_one_feature(features: dict, key: str) -> None:
        """Remove a single optional feature by its key.

        The docker and ssh features filter their apt packages out of the
        base apt-packages feature, keeping unrelated packages (ripgrep).
        """
        if key == "docker":
            DevcontainerGenerator._filter_apt_packages(
                features, DevcontainerGenerator.PODMAN_PACKAGES.split(",")
            )
            return
        if key == "ssh":
            DevcontainerGenerator._filter_apt_packages(
                features, [DevcontainerGenerator.SSH_APT_PACKAGE]
            )
            return
        url = DevcontainerGenerator.FEATURE_URL_MAP.get(key)
        if url is not None:
            features.pop(url, None)

    @staticmethod
    def _add_optional_features(
        features: dict,
        optional_features: List[str],
        java_build_tools: Optional[List[str]] = None,
    ) -> None:
        """Add optional features to the features dict.

        Uses variable substitution for configurable values with defaults.
        """
        for key in optional_features:
            DevcontainerGenerator._add_one_feature(features, key)

        # Reconcile Java build tools after all features are added
        if java_build_tools is not None:
            DevcontainerGenerator._reconcile_java_build_tools(
                features, java_build_tools
            )

    @staticmethod
    def detect_build_tools(devcontainer: dict) -> List[str]:
        """Detect currently-enabled Java build tools from devcontainer config.

        Args:
            devcontainer: Parsed devcontainer.json content

        Returns:
            List of enabled build tools (e.g. ["maven"], ["gradle"],
            ["maven","gradle"]). Empty when Java is present without
            explicit install flags.
        """
        raw_features = devcontainer.get("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        java_url = DevcontainerGenerator.FEATURE_URL_MAP.get("java")

        if java_url is None or java_url not in features:
            return []

        java_feature = features[java_url]
        if not isinstance(java_feature, dict):
            return []

        tools: List[str] = []
        if java_feature.get("installMaven"):
            tools.append("maven")
        if java_feature.get("installGradle"):
            tools.append("gradle")

        return tools

    @classmethod
    def detect(cls, devcontainer: dict) -> List[str]:
        """Detect currently-enabled optional features.

        The legacy ``docker-in-docker`` feature URL (pre-podman
        harnesses) is reported as the ``docker`` feature so the feature
        menu and reconcilers treat old configs as docker-enabled.

        Args:
            devcontainer: Parsed devcontainer.json content

        Returns:
            List of enabled optional feature keys
        """
        raw_features = devcontainer.get("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        detected = [key for key, url in cls.FEATURE_URL_MAP.items() if url in features]
        entry = features.get(cls.APT_PACKAGES_FEATURE_URL)
        packages = (
            [p.strip() for p in str(entry.get("packages", "")).split(",")]
            if isinstance(entry, dict)
            else []
        )
        has_docker = cls.LEGACY_DIND_FEATURE_URL in features or ("podman" in packages)
        if has_docker and "docker" not in detected:
            detected.append("docker")
        # The ssh feature's footprint is its apt package in the base
        # apt-packages entry (merged by _add_one_feature).
        if cls.SSH_APT_PACKAGE in packages and "ssh" not in detected:
            detected.append("ssh")
        return detected

    @classmethod
    def migrate_legacy_dind(
        cls, devcontainer: dict, active_features: List[str]
    ) -> bool:
        """Migrate the legacy docker-in-docker feature key to podman.

        Pre-podman harnesses carry the upstream ``docker-in-docker:2``
        feature; detect() reports it as the ``docker`` feature. The
        stale key is removed and, when docker stays active, the podman
        apt packages are merged into the base apt-packages feature so
        the rebuilt image carries the podman engine instead of the dead
        inner Docker daemon. A harness with docker deselected keeps the
        key removal only.

        Args:
            devcontainer: Parsed devcontainer.json content (mutated)
            active_features: Final feature selection after prompts

        Returns:
            True when a legacy key was migrated.
        """
        raw_features = devcontainer.setdefault("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        if raw_features is not features:
            devcontainer["features"] = features
        if cls.LEGACY_DIND_FEATURE_URL not in features:
            return False
        del features[cls.LEGACY_DIND_FEATURE_URL]
        if "docker" in active_features:
            cls._add_one_feature(features, "docker")
        return True

    @classmethod
    def apply_delta(
        cls,
        devcontainer: dict,
        add: List[str],
        remove: List[str],
        java_build_tools: Optional[List[str]] = None,
    ) -> dict:
        """Surgically apply feature changes to a devcontainer dict.

        Mutates the features dict in place, preserving any features and
        parameters that are not part of the requested change.

        Args:
            devcontainer: Parsed devcontainer.json content (mutated)
            add: Feature keys to add
            remove: Feature keys to remove
            java_build_tools: List of enabled Java build tools (for reconciliation)

        Returns:
            The same devcontainer dict, mutated.
        """
        raw_features = devcontainer.setdefault("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        if raw_features is not features:
            devcontainer["features"] = features
        for key in remove:
            cls._remove_one_feature(features, key)
        for key in add:
            cls._add_one_feature(features, key)

        # Reconcile Java build tools if Java is in the final feature set
        if java_build_tools is not None:
            cls._reconcile_java_build_tools(features, java_build_tools)

        return devcontainer
