#!/usr/bin/env bash
#
# AEON Railway Setup Helper
# =========================
# Provisions a Railway project, Postgres database, and deploys the AEON backend.
#
# Requirements:
#   - railway CLI installed and authenticated (npm install -g @railway/cli)
#   - git repo pushed to GitHub
#
# Authentication:
#   Either run `railway login` first, or set the RAILWAY_TOKEN environment variable.
#
# Usage:
#   ./scripts/setup-railway.sh [PROJECT_NAME]
#
set -euo pipefail

PROJECT_NAME="${1:-aeon-backend}"

echo "🚄 Setting up AEON backend on Railway..."

# Validate Railway CLI is available
if ! command -v railway &>/dev/null; then
  echo "❌ Railway CLI not found. Install it with: npm install -g @railway/cli"
  exit 1
fi

# Validate authentication (token or interactive login)
if [ -z "${RAILWAY_TOKEN:-}" ]; then
  if ! railway status &>/dev/null; then
    echo "❌ Not authenticated to Railway. Run 'railway login' or set RAILWAY_TOKEN."
    exit 1
  fi
  echo "🔗 Using interactive Railway login"
else
  echo "🔑 Using RAILWAY_TOKEN for authentication"
fi

# Create or link project
if ! railway status &>/dev/null; then
  echo "🔗 Creating Railway project: $PROJECT_NAME"
  railway init --name "$PROJECT_NAME"
else
  echo "🔗 Already linked to a Railway project"
fi

PROJECT_ID=$(railway project | grep -oE '[a-zA-Z0-9_-]{20,}' | head -1 || true)
if [ -z "$PROJECT_ID" ]; then
  echo " Could not determine Railway project ID"
  exit 1
fi

echo "📦 Project ID: $PROJECT_ID"

# Add PostgreSQL database
echo "🐘 Adding PostgreSQL database..."
railway add --database postgres --name "Postgres" || true

# Add backend service from GitHub repo
echo "🔧 Adding backend service..."
railway add --service "aeon-backend" || true

# Set required environment variables
echo "⚙️  Setting environment variables..."
railway variables --service "aeon-backend" set NEXTAUTH_SECRET "$(openssl rand -base64 32)"
railway variables --service "aeon-backend" set AEON_PYTHON_HOST "0.0.0.0"
railway variables --service "aeon-backend" set AEON_ROOT "/app/state"
railway variables --service "aeon-backend" set AEON_LLM_PROVIDER "stub"

# Optional: set these if you want real providers or admin seed
# railway variables --service "aeon-backend" set OPENAI_API_KEY "sk-..."
# railway variables --service "aeon-backend" set AEON_ADMIN_EMAIL "admin@aeon.local"
# railway variables --service "aeon-backend" set AEON_ADMIN_PASSWORD "..."

echo " Deploying backend..."
railway up --service "aeon-backend"

echo ""
echo "✅ Backend deployed!"
echo "   Public URL: $(railway domain --service aeon-backend 2>/dev/null || echo '<pending>')"
echo ""
echo "Next steps:"
echo "  1. Copy the backend public URL into your frontend env as AEON_PYTHON_URL"
echo "  2. Keep AUTH_SECRET in sync with the frontend"
echo "  3. Run: python scripts/healthcheck.py <backend_url>/health"
