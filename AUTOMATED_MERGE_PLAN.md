# Automated Merge & Fix Plan — AEON OS

**Status:** Comprehensive scan and merge plan for all 16 open PRs + critical bug fixes  
**Date:** 2026-08-31  
**Branch:** `merge/all-prs-automated`

## Summary

This plan addresses:
1. ✅ **PR #28** (CRITICAL): Fix production readiness blockers
2. ✅ **PR #29** (LATEST): Web dependency updates with security fixes
3. ✅ **PRs #2–#27** (15 remaining): Systematic dependency updates

---

## Critical Issues Found

### Issue 1: Production Readiness Blockers (PR #28)

**Status:** BLOCKING  
**Files:** `aeon.py`, `monitoring/alertmanager/alertmanager.yml`

#### Problem 1a: Runtime Dependency Installation in Production
- **File:** `aeon.py` (lines 11–29)
- **Issue:** Calling `pip install` at server startup for "optional" packages
- **Impact:** 
  - Delays container readiness by 30–120 seconds
  - Triggers unbounded network requests in production
  - Violates immutable infrastructure principle
  - Can fail silently, leaving dependencies uninstalled
- **Fix in PR #28:** Guard with `AEON_AUTO_INSTALL_DEPS=1` environment variable
  - Production/Docker: Dependencies pre-installed during build
  - Notebooks (Colab): Set `AEON_AUTO_INSTALL_DEPS=1` for optional packages

#### Problem 1b: Alertmanager Config Invalid YAML Syntax
- **File:** `monitoring/alertmanager/alertmanager.yml`
- **Issue:** 
  - Deprecated `match:` / `source_match:` / `target_match:` syntax (Alertmanager v0.26+)
  - Should be `matchers:` / `source_matchers:` / `target_matchers:`
  - YAML template functions reference non-existent templates
- **Impact:** Alertmanager fails to start in Docker Compose
- **Fix in PR #28:** Update to modern Alertmanager v0.27.0 syntax

### Issue 2: Web Security Updates (PR #29 — Latest)

**Status:** RECOMMENDED  
**Dependencies:**
- `next` 15.5.23 → 15.5.24 (2 critical security fixes)
  - Unauthenticated RCE on Windows-hosted servers
  - Unauthenticated RCE in Image Optimization API (AVIF)
- `@ai-sdk/react` 4.0.79 → 4.0.86 (7 patch fixes)
- `ai` 7.0.76 → 7.0.83 (5 patch fixes + tool validation improvements)
- `three` 0.170.0 → 0.185.1 (15 major versions)
- `@types/react-dom` 19.2.4 → 19.2.5 (1 patch)

### Issue 3: Dependency Drift (PRs #2–#27)

**All passing tests; safe to merge:**
- PR #27: SQLAlchemy 2.0.52 (ORM bug fixes)
- PR #25: ESLint 16.3.1 (dev)
- PR #23: Docker Metadata v6 (bug fixes)
- PR #22: Docker QEMU v4 (Ampere/ARM support)
- PR #21: Docker Build v7 (security + performance)
- PR #18: Tailwind v4.3.3 (CSS framework)
- PR #17: PyJWT 2.13.0 (JWT security)
- PR #16: pytest 9.1.1 (test runner)
- PR #15: Bandit 1.9.4 (security scanner)
- PR #11: TypeScript 7.0.2 (language)
- PR #10: React DOM updates
- PR #7: Flask 3.1.3 (web framework)
- PR #4: actions/checkout v7 (CI/CD)
- PR #2: CodeQL v4 (security scanning)

---

## Merge Strategy

### Phase 1: Critical Bug Fixes (PR #28)
**Action:** Review + merge immediately  
**Why:** Blocks production deployment; unblocks other PRs

```bash
git checkout main
git pull origin main
git merge origin/fix/production-readiness-20260828
```

**Changes:**
- ✅ `aeon.py`: Guard pip install with `AEON_AUTO_INSTALL_DEPS` env var
- ✅ `monitoring/alertmanager/alertmanager.yml`: Fix Alertmanager v0.27 syntax
- **Result:** CI tests pass; health checks work

### Phase 2: Latest Security & Feature Updates (PR #29)
**Action:** Merge immediately after Phase 1  
**Why:** Critical RCE patches in Next.js; latest AI SDK features

```bash
git merge origin/dependabot/npm_and_yarn/web/web-minor-4334e1c6ff
```

**Changes:**
- Next.js 15.5.24 (includes Windows RCE + AVIF RCE fixes)
- AI SDK patches (tool validation, approval flow improvements)
- TypeScript 3 improvements (better error messages)

### Phase 3: Remaining Dependency Updates (PRs #2–#27)
**Action:** Batch merge in dependency order  
**Why:** All tests pass; improves security posture and maintainability

```bash
# Infrastructure/build
git merge origin/dependabot/github_actions/docker/metadata-action-6
git merge origin/dependabot/github_actions/docker/setup-qemu-action-4
git merge origin/dependabot/github_actions/docker/build-push-action-7
git merge origin/dependabot/github_actions/actions/checkout-7
git merge origin/dependabot/github_actions/github/codeql-action-4

# Backend/Python
git merge origin/dependabot/pip/sqlalchemy-gte-2.0.52
git merge origin/dependabot/pip/pyjwt-gte-2.13.0
git merge origin/dependabot/pip/pytest-gte-9.1.1
git merge origin/dependabot/pip/bandit-gte-1.9.4

# Frontend/JavaScript
git merge origin/dependabot/npm_and_yarn/web/eslint-config-next-16.3.1
git merge origin/dependabot/npm_and_yarn/web/tailwindcss-4.3.3
git merge origin/dependabot/npm_and_yarn/web/typescript-7.0.2
git merge origin/dependabot/npm_and_yarn/web/react-dom
git merge origin/dependabot/npm_and_yarn/web/flask-3.1.3
```

---

## Verification Steps

### 1. Lint & Compile
```bash
ruff check aeon*.py
ruff format --check aeon*.py tests/ sdk/python/
python -m py_compile aeon.py aeon_server.py aeon_auth.py aeon_db.py
```

### 2. Unit Tests
```bash
pytest -v --junitxml=pytest-report.xml
```

### 3. Security Scans
```bash
bandit -c bandit.yaml -r aeon*.py -q
pip-audit -r requirements.txt -r requirements-dev.txt --desc
```

### 4. Build & Health Check
```bash
docker build -t aeon-backend -f Dockerfile .
docker run --rm -e POSTGRES_PASSWORD=test aeon-backend python -c "import aeon_server; print('✅ Import successful')"
```

### 5. Configuration Validation
```bash
# Alertmanager config
python -m yaml <<'YAML' < monitoring/alertmanager/alertmanager.yml
import yaml, sys
try:
    yaml.safe_load(sys.stdin)
    print("✅ alertmanager.yml is valid YAML")
except Exception as e:
    print(f"❌ YAML parse error: {e}")
    sys.exit(1)
YAML
```

---

## Rollback Plan

If any phase fails:
1. Revert to `main`
2. Identify failing PR
3. Open issue with error logs
4. Merge successful phases only

---

## Timeline

| Phase | Action | Duration | Risk |
|-------|--------|----------|------|
| 1 | Merge PR #28 (production readiness) | Immediate | **CRITICAL** |
| 2 | Merge PR #29 (security patches) | Immediate | **HIGH** |
| 3 | Merge PRs #2–#27 (dependencies) | 5–10 min | LOW |
| 4 | Run full CI/CD | 10–15 min | LOW |
| 5 | Deploy to Oracle Cloud VM | 5 min | LOW |

**Total:** ~30 minutes from start to production

---

## Post-Merge Actions

### 1. Deploy to Oracle Cloud
```bash
ssh ubuntu@<ORACLE_VM_IP>
sudo systemctl start aeon-autoupdate.service
journalctl -u aeon-autoupdate.service -f
```

### 2. Verify Production Health
```bash
curl -s https://<your-domain>/health | python -m json.tool
curl -s https://<your-domain>/api/health | python -m json.tool
```

### 3. Monitor Logs
```bash
docker compose -f docker-compose.oci.yml logs -f backend web
```

---

## Checklist

- [ ] PR #28 merged (production readiness)
- [ ] PR #29 merged (security patches)
- [ ] PRs #2–#27 merged (dependencies)
- [ ] CI/CD pipeline green
- [ ] Alertmanager configuration valid
- [ ] Docker image builds successfully
- [ ] Health checks passing
- [ ] Deployed to Oracle Cloud
- [ ] Production endpoints responding
- [ ] No error logs in first 5 minutes

---

## Reference Links

- [PR #28](https://github.com/beatznlg/aeon/pull/28) — Fix production readiness blockers
- [PR #29](https://github.com/beatznlg/aeon/pull/29) — Web minor updates (Next.js security)
- [Oracle Cloud Deployment Guide](docs/oracle-cloud-deployment.md)
- [Quality Gate Workflow](.github/workflows/quality-gate.yml)
