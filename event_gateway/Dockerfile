FROM node:20-slim AS deps

WORKDIR /app

COPY event_gateway/package*.json /app/
RUN npm ci --omit=dev

FROM node:20-slim AS runtime

WORKDIR /app

COPY --from=deps /app/node_modules /app/node_modules
COPY event_gateway /app

CMD ["node", "src/server.mjs"]
