#!/usr/bin/env bash
# Idempotent seed: ensure admin user + membership on the existing default workspace
set -e
cd /opt/aeon
set -a; source .env; set +a

./venv/bin/python - <<'PYEOF'
import os, sys
sys.path.insert(0, '/opt/aeon')
from werkzeug.security import generate_password_hash
from aeon_db import get_db, User, Workspace, Membership

db = get_db()
email = os.environ['AEON_ADMIN_EMAIL']
password = os.environ['AEON_ADMIN_PASSWORD']

with db.session() as s:
    ws = s.query(Workspace).filter_by(slug='default').first()
    if not ws:
        ws = Workspace(slug='default', name='Default Workspace', plan='free')
        s.add(ws); s.flush()

    user = s.query(User).filter_by(email=email).first()
    if not user:
        user = User(email=email, name=os.environ.get('AEON_ADMIN_NAME', 'Admin'),
                    password=generate_password_hash(password), role='ADMIN')
        s.add(user); s.flush()
        print('USER_CREATED')
    else:
        print('USER_EXISTS')

    m = s.query(Membership).filter_by(workspace_id=ws.id, user_id=user.id).first()
    if not m:
        s.add(Membership(workspace_id=ws.id, user_id=user.id, role='ADMIN'))
        print('MEMBERSHIP_ADDED')
    else:
        print('MEMBERSHIP_OK')
print('SEED_DONE')
PYEOF
