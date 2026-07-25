# AEON OS — Next.js Frontend
# ===========================
# Multi-stage Docker image for the AEON web dashboard.
#
# Build:
#   docker build -t aeon-frontend -f web/Dockerfile web/
# Run:
#   docker run -p 3000:3000 aeon-frontend
#
# Environment variables (see .env.example):
#   AEON_PYTHON_URL       (required — http://aeon-backend:5000)
#   NEXTAUTH_URL           (required — http://localhost:3000)
#   NEXTAUTH_SECRET        (required — generate with `openssl rand -base64 32`)
#   SUPABASE_URL           (optional)
#   SUPABASE_ANON_KEY      (optional)
#   SUPABASE_SERVICE_ROLE_KEY (optional)

# ─── Stage 1: Install & Build ──────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Install build dependencies
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
RUN npm run build

# Prune dev dependencies for smaller runtime
RUN npm prune --production

# ─── Stage 2: Runtime ──────────────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built application
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.* ./ 2>/dev/null || true
COPY --from=builder /app/next-env.d.ts ./ 2>/dev/null || true

USER nextjs

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "start"]
