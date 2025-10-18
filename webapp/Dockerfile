# Stage 1: Build the frontend app
FROM --platform=$BUILDPLATFORM node:20-alpine AS builder

# Set working directory
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Copy the rest of the application
COPY . .

# Build the production-ready static files
RUN npm run build

# Stage 2: Serve with minimal NGINX
FROM nginx:1.25-alpine AS serve

# Remove default NGINX config
#RUN rm /etc/nginx/conf.d/default.conf

# Copy custom NGINX config
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# Copy built frontend from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

# Start NGINX
CMD ["nginx", "-g", "daemon off;"]