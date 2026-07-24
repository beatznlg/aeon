# AEON Next.js Web Frontend — Production Dockerfile
#
# Build:
#   docker build -t aeon-web:latest .
#
# Run:
#   docker run -p 3000:3000 -e AEON_PYTHON_URL=http://aeon-server:5000 aeon-web:latest

FROM node:20-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]
