# Branch Protection Setup

This guide walks through the recommended branch protection rules for the `main` branch of `beatznlg/aeon`. These settings can only be changed by a repository admin through the GitHub UI.

## Why branch protection matters

Branch protection ensures that:

- Code on `main` has been reviewed before it lands
- Required CI checks pass before merging
- Force pushes and deletions are blocked
- CODEOWNERS approval is required for security-critical files

## Settings to apply

1. Go to **https://github.com/beatznlg/aeon/settings/branches**
2. Under **Branch protection rules**, click **Add rule**
3. For **Branch name pattern**, enter: `main`
4. Enable the following options:

### Protect matching branches

- ✅ **Require a pull request before merging**
  - ✅ **Require approvals**: `1`
  - ✅ **Dismiss stale PR approvals when new commits are pushed**
  - ✅ **Require review from CODEOWNERS**

- ✅ **Require status checks to pass before merging**
  - Search for and select:
    - `smoke-check`
    - `web-build-check`

- ✅ **Require conversation resolution before merging`

- ✅ **Require signed commits` (recommended)

### Additional settings

- ✅ **Restrict pushes that create files larger than 100 MB`
- ✅ **Require linear history` (optional, but recommended)
- ✅ **Do not allow bypassing the above settings` (for admins too)

### Branch restrictions

- ✅ **Restrict who can push to matching branches`
  - Add the project maintainers team or `@beatznlg`

## What this enforces

With these rules in place:

- Direct pushes to `main` are blocked
- PRs must have at least one approving review
- PRs touching files owned by CODEOWNERS must be approved by `@beatznlg`
- The `aeon-ci` workflow (smoke-check + web-build-check) must pass
- Stale approvals are automatically dismissed when new commits are pushed

## Admin-only alternatives

If you prefer to automate branch protection, you can use the GitHub API with an repository admin PAT:

```bash
# Example: require PR reviews, status checks, and CODEOWNERS
gh api -X POST repos/beatznlg/aeon/rulesets \
  -H "Accept: application/vnd.github+json" \
  -f name="Protect main" \
  -f target=branch \
  -f conditions='{"ref_name":{"include":["main"],"exclude":[]}}' \
  -f rules='{"required_pull_request_reviews":{"required_approving_review_count":1,"require_code_owner_reviews":true,"dismiss_stale_reviews":true},"required_status_checks":[{"context":"smoke-check"},{"context":"web-build-check"}],"required_linear_history":true,"non_fast_forward":true}' \
  -f enforcement=active
```

> Note: The Freebuff GitHub App credential used in this workspace does not currently have admin permissions, so these settings must be applied by a repository admin manually or with an admin-scoped PAT.

## Verifying the rules

After setup, try pushing directly to `main` from a local clone. You should see an error like:

```
remote: error: GH006: The protected branch 'main' requires a pull request.
```

Create a test PR from a feature branch. The merge button should remain disabled until:

- At least one review is approved
- `smoke-check` and `web-build-check` are green
- All review comments are resolved
