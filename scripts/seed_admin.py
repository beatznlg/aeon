"""Idempotently ensure the configured AEON admin user exists.

Invoked by scripts/docker-entrypoint.sh on every backend start when
AEON_ADMIN_EMAIL + AEON_ADMIN_PASSWORD are set in the environment.
Behavior:
  - user missing            -> create ADMIN user + 'default' workspace + membership
  - user exists             -> ensure workspace/membership only
  - AEON_ADMIN_RESET_PASSWORD=true -> also overwrite the stored password hash
Reads credentials exclusively from the process environment (never interpolated
into source code), so passwords may contain any characters safely.
"""
import os
import sys

# Work both inside the Docker image (/app) and from a repo checkout
# (e.g. legacy venv runs: python3 scripts/seed_admin.py).
_HERE = os.path.dirname(os.path.abspath(__file__))
for _candidate in ("/app", os.path.dirname(_HERE), _HERE):
    if os.path.isdir(_candidate) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from werkzeug.security import generate_password_hash  # noqa: E402

from aeon_db import Membership, User, Workspace, get_db  # noqa: E402


def main() -> int:
    email = (os.environ.get("AEON_ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("AEON_ADMIN_PASSWORD") or ""
    reset_password = (os.environ.get("AEON_ADMIN_RESET_PASSWORD") or "").lower() == "true"
    admin_name = os.environ.get("AEON_ADMIN_NAME") or "Admin"

    if not email or not password:
        return 0  # not configured — skip silently (self-service signup still works)

    db = get_db()

    with db.session() as session:
        workspace = session.query(Workspace).filter_by(slug="default").first()
        if not workspace:
            workspace = Workspace(slug="default", name="Default Workspace", plan="free")
            session.add(workspace)
            session.flush()

        user = session.query(User).filter_by(email=email).first()
        if not user:
            user = User(
                email=email,
                name=admin_name,
                password=generate_password_hash(password),
                role="OWNER",
            )
            session.add(user)
            session.flush()
            print(f"[seed] super admin (OWNER) user created: {email}")
        elif reset_password:
            user.password = generate_password_hash(password)
            user.role = "OWNER"
            print(f"[seed] admin password updated & role upgraded to OWNER: {email}")
        else:
            if user.role != "OWNER":
                user.role = "OWNER"
                print(f"[seed] admin role upgraded to OWNER: {email}")
            else:
                print(f"[seed] admin user exists: {email}")

        membership = (
            session.query(Membership)
            .filter_by(workspace_id=workspace.id, user_id=user.id)
            .first()
        )
        if not membership:
            session.add(
                Membership(workspace_id=workspace.id, user_id=user.id, role="OWNER")
            )
            print("[seed] OWNER membership ensured on workspace 'default'")
        elif membership.role != "OWNER":
            membership.role = "OWNER"
            print("[seed] membership role upgraded to OWNER")

        # Plain sessions do NOT auto-commit on context exit — without this
        # everything above is rolled back when the block closes.
        session.commit()

    print("[seed] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
