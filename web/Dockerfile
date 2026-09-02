# AEON OS — Next.js frontend container (multi-stage, ARM64/x64 compatible)
# Used by docker-compose.yml on Oracle Cloud (Ampere A1 or x86 VMs).

FROM node:20-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM node:20-slim AS builder
WORKDIR /app
# Auth.js throws at module load when the secret is < 32 chars during the
# production build's page-data collection. A placeholder lets the image build
# anywhere (Cloud Build has no secrets); the real AUTH_SECRET is injected at
# runtime by Cloud Run / compose and overrides this image-level ENV.
ARG AUTH_SECRET=build-time-only-placeholder-secret-0123456789abcdef
ENV AUTH_SECRET=$AUTH_SECRET \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 1001 nodejs && useradd -u 1001 -g nodejs -m nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Pre-create the offline-registration store directory as the unprivileged
# runtime user. Without this, the named volume (web_data) is first mounted
# root-owned at /app/.data and the nextjs user cannot write it, which made
# every local-store registration fail (surfacing as EMAIL_TAKEN).
RUN mkdir -p /app/.data && chown -R nextjs:nodejs /app/.data

USER nextjs
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3000/api/health || exit 1
CMD ["node", "server.js"]
