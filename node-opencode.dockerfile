FROM node:25-trixie
RUN apt update && apt install -y ca-certificates curl
RUN install -m 0755 -d /etc/apt/keyrings && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt update
RUN apt-get install -y --no-install-recommends nano docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
RUN apt clean && && rm -rf /var/lib/apt/lists/*
RUN yarn global add opencode-ai@1.2.27