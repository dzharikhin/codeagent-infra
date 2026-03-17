FROM node:25-trixie
RUN apk update
RUN apk add --no-cache nano docker docker-compose
RUN yarn global add opencode-ai@1.2.27