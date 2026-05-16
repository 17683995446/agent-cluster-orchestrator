# Multi-stage Docker build for Agent Cluster Orchestrator Frontend
# Stage 1: Base image
FROM node:18-alpine as base

WORKDIR /app

# Stage 2: Builder
FROM base as builder

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build application
RUN npm run build

# Stage 3: Production with Nginx
FROM nginx:alpine as production

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

# Stage 4: Development
FROM base as development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
