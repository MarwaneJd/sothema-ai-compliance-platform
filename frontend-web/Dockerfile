# ───────────────────────────────────────────────────
# Stage 1: build the SPA bundle
# ───────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

# Build-time env (Vite bakes these into the bundle)
ARG VITE_USE_MOCK=false
ARG VITE_API_BASE_URL=http://localhost:5000
ARG VITE_AZURE_CLIENT_ID=
ARG VITE_AZURE_TENANT_ID=
ENV VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID \
    VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ───────────────────────────────────────────────────
# Stage 2: serve with Nginx (non-root)
# ───────────────────────────────────────────────────
FROM nginx:alpine AS runtime

# nginx:alpine ships an `nginx` user already; switch to it.
# Cache and pid paths must be writable by that user.
RUN chown -R nginx:nginx /var/cache/nginx /var/run \
 && touch /var/run/nginx.pid \
 && chown nginx:nginx /var/run/nginx.pid

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

USER nginx

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
