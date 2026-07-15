# =============================================================================
# IDM-Core Dashboard (Next.js 14) - Dockerfile
# =============================================================================
# ⚠️  NO construye con `context: ./frontend`. Desde el retheme del design-system
# (2026-06-20), `tailwind.config.js` y `src/app/globals.css` importan el
# design-system compartido en `projects/design-system/`, que queda FUERA de este
# contexto → `next build` falla con "Cannot find module
# '../../design-system/tailwind.preset.cjs'". Para construir el dashboard usa
# `Dockerfile.root` desde la raíz de projects (así lo hace micelia/docker-compose.yml
# → idm-dashboard). Este fichero se conserva solo como referencia histórica.
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder - install deps and build the Next.js app
# ---------------------------------------------------------------------------
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source and build
COPY . .

# Set the API URL for build-time (rewrites are runtime, but some components
# may use NEXT_PUBLIC_ env vars)
ENV NEXT_PUBLIC_IDM_CORE_URL=http://idm-core:8888

RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Production - lean runtime image
# ---------------------------------------------------------------------------
FROM node:18-alpine AS production

WORKDIR /app

# Install curl for health checks
RUN apk add --no-cache curl

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nextjs -u 1001

# Copy built app from builder (with correct ownership for non-root user)
COPY --from=builder --chown=nextjs:nodejs /app/package.json ./
COPY --from=builder --chown=nextjs:nodejs /app/node_modules ./node_modules
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder --chown=nextjs:nodejs /app/next.config.js ./

USER nextjs

EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:9000/ || exit 1

CMD ["npx", "next", "start", "-p", "9000"]
