#!/bin/sh
# ============================================================================
# AEON OS — one-shot GCP CI/CD activation (idempotent; safe to re-run)
#
# Run from Cloud Shell, inside your aeon checkout:
#     cd ~/aeon && git pull origin main && sh scripts/setup-gcp-cicd.sh
#
# What it does (in order):
#   1. Enables the required Google Cloud APIs
#   2. Ensures the Artifact Registry docker repository exists
#   3. Grants the Cloud Build service account the deploy roles
#   4. Fixes the 'aeon-main' push trigger: no manual approval + correct SA
#   5. Cancels stale approval-blocked builds, then runs the first full build
#      (pytest -> build backend+frontend images -> deploy both to Cloud Run)
#   6. Wires aeon-web env (backend URL, auth) WITHOUT touching other vars
#   7. Verifies backend /health and frontend /api/health, prints the URLs
#
# After this succeeds once: every push to main (e.g. saving from Freebuff)
# deploys automatically. Cloud SQL, existing env vars, and service accounts
# on the running services are never touched by deploys — only images change.
# ============================================================================
set -eu

REGION="${AEON_GCP_REGION:-europe-west1}"
REPO_OWNER="${AEON_REPO_OWNER:-beatznlg}"
REPO_NAME="${AEON_REPO_NAME:-aeon}"
TRIGGER_NAME="aeon-main"
BRANCH="main"

say()  { printf '\n===> %s\n' "$1"; }
info() { printf '    %s\n' "$1"; }
warn() { printf '    WARNING: %s\n' "$1" >&2; }

command -v gcloud >/dev/null 2>&1 || { echo "ERROR: gcloud not found. Run this in Cloud Shell." >&2; exit 1; }
command -v git    >/dev/null 2>&1 || { echo "ERROR: git not found." >&2; exit 1; }
command -v curl   >/dev/null 2>&1 || { echo "ERROR: curl not found." >&2; exit 1; }

REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_DIR"
[ -f cloudbuild.yaml ] || { echo "ERROR: run this script inside the aeon repository checkout." >&2; exit 1; }

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
[ -n "$PROJECT_ID" ] && [ "$PROJECT_ID" != "None" ] || {
  echo "ERROR: no active gcloud project. Run: gcloud config set project <project-id>" >&2
  exit 1
}
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

say "Project: $PROJECT_ID | Region: $REGION | Cloud Build SA: $BUILD_SA"

# 1 ─ APIs ───────────────────────────────────────────────────────────────────
say "Step 1/7: enabling required APIs"
gcloud services enable \
  cloudbuild.googleapis.com run.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com \
  --quiet

# 2 ─ Artifact Registry ──────────────────────────────────────────────────────
say "Step 2/7: ensuring Artifact Registry repository exists"
if gcloud artifacts repositories describe "$REPO_NAME" --location="$REGION" >/dev/null 2>&1; then
  info "repository '$REPO_NAME' already exists"
else
  gcloud artifacts repositories create "$REPO_NAME" \
    --repository-format=docker --location="$REGION" --quiet
  info "created repository '$REPO_NAME'"
fi

# 3 ─ IAM roles for Cloud Build ──────────────────────────────────────────────
say "Step 3/7: granting deployment roles to the Cloud Build service account"
for ROLE in roles/run.admin roles/iam.serviceAccountUser roles/artifactregistry.writer; do
  if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member "serviceAccount:$BUILD_SA" --role "$ROLE" --quiet >/dev/null 2>&1; then
    info "granted $ROLE"
  else
    info "$ROLE already present (or skipped)"
  fi
done

# 4 ─ Fix the push trigger ───────────────────────────────────────────────────
say "Step 4/7: fixing push trigger '$TRIGGER_NAME' (auto-run, correct service account)"
if gcloud builds triggers describe "$TRIGGER_NAME" >/dev/null 2>&1; then
  if gcloud builds triggers update github "$TRIGGER_NAME" \
      --no-require-approval \
      --service-account "projects/$PROJECT_ID/serviceAccounts/$BUILD_SA" \
      --branch-pattern "^$BRANCH\$" \
      --build-config cloudbuild.yaml \
      --repo-name "$REPO_NAME" --repo-owner "$REPO_OWNER" >/dev/null 2>&1 \
     || gcloud builds triggers update "$TRIGGER_NAME" \
      --no-require-approval \
      --service-account "projects/$PROJECT_ID/serviceAccounts/$BUILD_SA" >/dev/null 2>&1; then
    info "trigger fixed — pushes to '$BRANCH' now build and deploy automatically"
  else
    warn "could not update the trigger from the CLI — do it in the Console (2 min):"
    warn "  Console -> Cloud Build -> Triggers -> $TRIGGER_NAME -> EDIT:"
    warn "    - uncheck 'Require approval'"
    warn "    - Service account: $BUILD_SA"
  fi
else
  info "trigger '$TRIGGER_NAME' not found — trying to create it"
  if gcloud builds triggers create github \
      --name "$TRIGGER_NAME" \
      --repo-name "$REPO_NAME" --repo-owner "$REPO_OWNER" \
      --branch-pattern "^$BRANCH\$" \
      --build-config cloudbuild.yaml \
      --no-require-approval \
      --service-account "projects/$PROJECT_ID/serviceAccounts/$BUILD_SA" >/dev/null 2>&1; then
    info "trigger created"
  else
    warn "automatic trigger creation failed — the GitHub App connection needs a one-time browser click:"
    warn "  Console -> Cloud Build -> Triggers -> Create trigger -> Connect repository -> $REPO_OWNER/$REPO_NAME"
  fi
fi

# 5 ─ First (or in-flight) build ─────────────────────────────────────────────
say "Step 5/7: checking for builds already queued by recent pushes"
ACTIVE=$(gcloud builds list \
  --filter="buildTriggerId=$TRIGGER_NAME AND (status=PENDING OR status=QUEUED OR status=WORKING)" \
  --format='value(id)' --limit=1 2>/dev/null || true)

if [ -n "$ACTIVE" ]; then
  STATUS=$(gcloud builds describe "$ACTIVE" --format='value(status)' 2>/dev/null || echo UNKNOWN)
  if [ "$STATUS" = "PENDING" ]; then
    info "build $ACTIVE is stuck waiting for approval (old trigger settings) — cancelling it"
    gcloud builds cancel "$ACTIVE" --quiet >/dev/null 2>&1 || true
    ACTIVE=""
  fi
fi

if [ -n "$ACTIVE" ]; then
  info "build $ACTIVE is already running — waiting for it to finish (up to ~25 min)"
  i=0
  while [ "$i" -lt 150 ]; do
    STATUS=$(gcloud builds describe "$ACTIVE" --format='value(status)' 2>/dev/null || echo UNKNOWN)
    case "$STATUS" in
      SUCCESS) info "build $ACTIVE succeeded"; break ;;
      FAILURE|INTERNAL_ERROR|TIMEOUT|CANCELLED|EXPIRED)
        warn "build $ACTIVE finished with status $STATUS"
        warn "logs: gcloud builds log $ACTIVE   (re-run this script afterwards)"
        exit 1 ;;
    esac
    i=$((i + 1))
    sleep 10
  done
  if [ "$STATUS" != "SUCCESS" ]; then
    warn "timed out waiting for build $ACTIVE"
    exit 1
  fi
else
  say "Step 5/7: submitting the full build (pytest -> images -> Cloud Run deploy)"
  COMMIT_SHA=$(git rev-parse HEAD)
  info "commit $COMMIT_SHA — this streams build logs, typically 10-15 min"
  if ! gcloud builds submit --config cloudbuild.yaml \
      --substitutions "COMMIT_SHA=$COMMIT_SHA" .; then
    warn "build failed — read the log above, fix, and re-run this script"
    exit 1
  fi
fi

# 6 ─ Frontend environment ───────────────────────────────────────────────────
say "Step 6/7: wiring frontend environment (existing env vars are preserved)"
API_URL=$(gcloud run services describe aeon-api --region "$REGION" --format='value(status.url)')
WEB_URL=$(gcloud run services describe aeon-web --region "$REGION" --format='value(status.url)')
info "backend:  $API_URL"
info "frontend: $WEB_URL"

NEED_SECRET=1
CURRENT_ENV=$(gcloud run services describe aeon-web --region "$REGION" \
  --format='value(spec.template.spec.containers[0].env)' 2>/dev/null || true)
case "$CURRENT_ENV" in
  *AUTH_SECRET*) NEED_SECRET=0 ;;
esac

ENV_UPDATE="AEON_PYTHON_URL=$API_URL,NEXTAUTH_URL=$WEB_URL,AUTH_TRUST_HOST=true"
if [ "$NEED_SECRET" -eq 1 ]; then
  AUTH_SECRET=$(openssl rand -hex 32)
  ENV_UPDATE="$ENV_UPDATE,AUTH_SECRET=$AUTH_SECRET"
  unset AUTH_SECRET
  info "generated a new AUTH_SECRET (none was set)"
else
  info "AUTH_SECRET already set — left untouched"
fi

gcloud run services update aeon-web --region "$REGION" \
  --update-env-vars "$ENV_UPDATE" --quiet >/dev/null
info "aeon-web env updated: AEON_PYTHON_URL, NEXTAUTH_URL, AUTH_TRUST_HOST (+ AUTH_SECRET if new)"

# 7 ─ Verify ─────────────────────────────────────────────────────────────────
say "Step 7/7: verifying the deployment"

if gcloud sql instances list --format='value(name)' 2>/dev/null | grep -qx 'aeon-postgres'; then
  info "Cloud SQL instance 'aeon-postgres' present (database 'aeon')"
else
  warn "Cloud SQL instance 'aeon-postgres' not found in this project"
fi

wait_ok() {
  # wait_ok <url> <grep-needle> <label>
  i=0
  while [ "$i" -lt 30 ]; do
    if curl -fsS "$1" 2>/dev/null | grep -q "$2"; then
      info "$3 is healthy"
      return 0
    fi
    i=$((i + 1))
    sleep 5
  done
  warn "$3 did not become healthy within 150s"
  return 1
}

BACKEND_OK=0
FRONTEND_OK=0
wait_ok "$API_URL/health" '"ok":true' "backend  ($API_URL/health)"  && BACKEND_OK=1 || true
wait_ok "$WEB_URL/api/health" . "frontend ($WEB_URL/api/health)" && FRONTEND_OK=1 || true

say "Setup complete"
echo
echo "  Dashboard : $WEB_URL"
echo "  API       : $API_URL"
if [ "$BACKEND_OK" -eq 1 ] && [ "$FRONTEND_OK" -eq 1 ]; then
  echo "  Health    : backend OK, frontend OK"
else
  echo "  Health    : see warnings above — services may still be starting"
fi
echo
echo "  From now on: save changes in Freebuff -> push to main -> Cloud Build"
echo "  tests, builds, and deploys both services automatically."
echo
echo "  Watch builds  : gcloud builds list --limit=5"
echo "  Trigger state : gcloud builds triggers describe $TRIGGER_NAME"
echo "  Backend logs  : gcloud run services logs read aeon-api  --region $REGION"
echo "  Frontend logs : gcloud run services logs read aeon-web --region $REGION"
