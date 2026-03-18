FROM node:25-trixie
RUN apt update
RUN apt-get install -y --no-install-recommends nano docker docker-compose
RUN apt clean && && rm -rf /var/lib/apt/lists/*
RUN yarn global add opencode-ai@1.2.27