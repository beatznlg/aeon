#!/bin/sh

# Copy root env vars into the web/ app so Next.js loads them at startup.
# This bridges Freebuff's monorepo root .env.local with Next.js's
# expectation of a .env.local in the app directory.
if [ -f ".env.local" ]; then
  cp .env.local web/.env.local
fi

# Start the Next.js dev server bound to all interfaces.
# Uses the platform-injected PORT when set (Freebuff isolated workspaces),
# otherwise falls back to the standard 3000.
cd web && npm run dev -- -H 0.0.0.0 -p ${PORT:-3000}
