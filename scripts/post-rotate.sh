#!/usr/bin/env bash
# scripts/post-rotate.sh
#
# AFTER-AEON-DOES-ITS-PART printable checklist.
# This is a printer-only script — it makes zero network calls and changes
# nothing. Run it once for the full step-by-step rotation instructions for
# any tokens you have already pasted in chat this session.
#
# Usage: bash scripts/post-rotate.sh
set -euo pipefail

cat <<'EOF'

================================================================================
  STEP 1 / 4  —  ROTATE THE GITHUB PAT  (leaked earlier in this session)
================================================================================
The token starting with  ghp_G6AU78JG6ez  was shared in chat. Treat it as
fully compromised regardless of whether the chat is "private".

  1. Open the rotation page:
       https://github.com/settings/tokens
  2. Find the row whose note contains "aeon" (or the date you created it).
  3. Click  Delete  on the right side of the row.
  4. Click  Generate new token  (fine-grained, beta):
         - Token name: aeon-deploy-2026
         - Expiration: 30 days  (rotate sooner next month)
         - Repository access: Public Repositories (read-only)
         - Account permissions: none
  5. Copy the new token (it starts with github_pat_...).
  6. Paste it ONLY into one of these, never into chat:
       - this dev env's  Keys / Secrets  tab   as  GH_TOKEN
       - or, your Vercel dashboard env vars   as  GH_TOKEN
  7. Verify on your machine:  gh auth status  (should print "Logged in to
     github.com as <your-username>" with the new token).


================================================================================
  STEP 2 / 4  —  ROTATE THE SUPABASE SERVICE-ROLE KEY  (leaked earlier)
================================================================================
The token starting with  sb_secret_LmvI-DGy  was shared in chat. Same
treatment: rotate now.

  1. Open the Supabase dashboard:
       https://supabase.com/dashboard
  2. Select your AEON project.
  3. Left sidebar  ▸  Project Settings  ▸  API
  4. Scroll to  "Service role secret JWT"  and click  Rotate Secret Key.
     Supabase will warn that this invalidates all callers using the old key
     — click  "I understand, rotate key"  to confirm.
  5. The new value appears in a "Show" dialog.  Copy it once.
       (You will NOT be able to view it again without rotating again.)
  6. Paste it ONLY into one of these, never into chat:
       - this dev env's  Keys / Secrets  tab   as  SUPABASE_SERVICE_ROLE_KEY
       - or, your Vercel dashboard env vars   as  SUPABASE_SERVICE_ROLE_KEY
     ALSO rotate SUPABASE_ANON_KEY if you used the anon JWT in chat (you did).
  7. Run the AEON kernel once locally and confirm:
       python -c "from aeon import SBC; print(SBC.whoami(), SBC.ping())"
     → "ok": True,  "rows": <nonnegative>


================================================================================
  STEP 3 / 4  —  AUDIT WHAT EVERYONE ELSE CAN DO WITH THE OLD SECRETS
================================================================================
Two lightweight checks.  Both are read-only.

  GitHub PAT:
    Open   https://github.com/settings/security-log
    Filter by the date range since the first paste.
    Look for unexpected clones, push events, or settings changes tied to your
    account.  If anything looks unfamiliar, also rotate any SSO / OAuth tokens
    and enable 2FA hardware-key if you have not.

  Supabase service-role key:
    Open   https://supabase.com/dashboard/project/_/editor
    Click the  episodes  table  →  Row Level Security tab.
    Look for inserts / updates you did NOT make since the first paste.  The
    service-role key bypasses RLS, so anything in that table from that day
    could be unintended.


================================================================================
  STEP 4 / 4  —  PASTE THE NEW KEYS INTO  Key / Secrets  TABS, NOT HERE
================================================================================
Targets (paste fresh values INTO these, never re-paste into chat):

  Local dev (this sandbox):
      HUGGINGFACE_TOKEN        (new value from https://huggingface.co/settings/tokens)
      SUPABASE_URL             (from Supabase dashboard; starts https://, ends .supabase.co)
      SUPABASE_SERVICE_ROLE_KEY  (rotated in Step 2)
      GH_TOKEN                 (rotated in Step 1; github_pat_... form recommended)

  Vercel project env vars  (Project Settings ▸ Environment Variables):
      HUGGINGFACE_TOKEN                  (server)
      NEXT_PUBLIC_SUPABASE_URL           (browser-visible)
      NEXT_PUBLIC_SUPABASE_ANON_KEY      (browser-visible)
      AEON_HF_SPACE_URL                  (server, your HF Space URL)
      SUPABASE_SERVICE_ROLE_KEY          (server)
      GH_TOKEN                           (server)

  Hugging Face Space env  (your new Space's Variables and secrets tab):
      HUGGINGFACE_TOKEN                  (Space secret)


Once the leak is closed, run  bash scripts/deploy-vercel.sh  to push the live
URL, then  bash scripts/deploy-hf-space.sh  to spin up the AEON kernel
behind it.

================================================================================
EOF
echo
echo "(Printer-only script — nothing was changed on disk and no network was touched.)"
