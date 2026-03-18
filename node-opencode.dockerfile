FROM node:25-trixie
RUN apt update
RUN apt install --no-cache nano docker docker-compose
RUN yarn global add opencode-ai@1.2.27