FROM node:25-trixie
RUN apt update
RUN apt install ca-certificates curl
RUN install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    (tee /etc/apt/sources.list.d/docker.sources <<EOF \
Types: deb \
URIs: https://download.docker.com/linux/ubuntu \
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") \
Components: stable \
Signed-By: /etc/apt/keyrings/docker.asc \
EOF \
) && apt update
RUN apt-get install -y --no-install-recommends nano docker docker-compose
RUN apt clean && && rm -rf /var/lib/apt/lists/*
RUN yarn global add opencode-ai@1.2.27