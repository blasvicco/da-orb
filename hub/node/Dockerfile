FROM node:22-alpine

WORKDIR /deps
COPY app/frontend/package.json app/frontend/yarn.lock ./
RUN yarn install --frozen-lockfile

ENV PATH=/deps/node_modules/.bin:$PATH

WORKDIR /home/app
