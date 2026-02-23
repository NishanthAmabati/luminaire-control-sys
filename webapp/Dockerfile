FROM node:20-slim AS builder

WORKDIR /app

COPY webapp/package*.json /app/
RUN npm ci

COPY webapp /app
COPY config.yaml /app/public/config.yaml

ARG VITE_API_URL
ARG VITE_EVENT_GATEWAY_URL
ARG VITE_UI_CONFIG_URL

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_EVENT_GATEWAY_URL=$VITE_EVENT_GATEWAY_URL
ENV VITE_UI_CONFIG_URL=$VITE_UI_CONFIG_URL

RUN npm run build

FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
