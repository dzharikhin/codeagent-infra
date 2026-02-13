FROM node:25-alpine
RUN apk update
RUN apk add --no-cache docker docker-compose
RUN yarn global add opencode-ai@1.1.65