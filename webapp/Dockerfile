FROM node:20-slim AS builder

WORKDIR /app

COPY webapp/package*.json /app/
RUN npm ci

COPY webapp /app
# COPY config.yaml /app/public/config.yaml

ARG VITE_API_URL
ARG VITE_EVENT_GATEWAY_URL
ARG VITE_UI_CONFIG_URL

ENV VITE_API_URL=$VITE_API_URL
ENV VITE_EVENT_GATEWAY_URL=$VITE_EVENT_GATEWAY_URL
ENV VITE_UI_CONFIG_URL=$VITE_UI_CONFIG_URL

RUN npm run build

FROM nginx:alpine

ARG TIMEZONE

RUN apk add --no-cache tzdata

ENV TZ=$TIMEZONE

COPY --from=builder /app/dist /usr/share/nginx/html
COPY webapp/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

RUN addgroup -S -g 1001 appgroup && \
    adduser -S -u 1001 -G appgroup -s /sbin/nologin appuser && \
    chown -R appuser:appgroup /usr/share/nginx/html && \
    chown -R appuser:appgroup /var/cache/nginx && \
    touch /var/run/nginx.pid && \
    chown appuser:appgroup /var/run/nginx.pid
USER appuser

CMD ["nginx", "-g", "daemon off;"]
