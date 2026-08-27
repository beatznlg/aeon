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

sys.path.insert(0, "/app")

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
                role="ADMIN",
            )
            session.add(user)
            session.flush()
            print(f"[seed] admin user created: {email}")
        elif reset_password:
            user.password = generate_password_hash(password)
            print(f"[seed] admin password updated: {email}")
        else:
            print(f"[seed] admin user exists: {email}")

        membership = (
            session.query(Membership)
            .filter_by(workspace_id=workspace.id, user_id=user.id)
            .first()
        )
        if not membership:
            session.add(
                Membership(workspace_id=workspace.id, user_id=user.id, role="ADMIN")
            )
            print("[seed] ADMIN membership ensured on workspace 'default'")

    print("[seed] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
