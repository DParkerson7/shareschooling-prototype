"""One-off password reset. Refuses to run unless ADMIN_RESET=yes.

    ADMIN_RESET=yes ADMIN_EMAIL=... ADMIN_PASSWORD=... DATABASE_URL=... TOKEN_SECRET=... \\
        python -m api.reset_admin

Do not put those values in the git repo.
"""

import os
import sys

from api.app import create_app


def main():
    if os.environ.get("ADMIN_RESET") != "yes":
        print("Refusing to reset. Set ADMIN_RESET=yes for this one command.", file=sys.stderr)
        return 1
    email = os.environ.get("ADMIN_EMAIL", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if not email or not password:
        print("Set ADMIN_EMAIL and ADMIN_PASSWORD in the environment.", file=sys.stderr)
        return 1
    app = create_app()
    app.service.reset_admin_password(email, password)
    print("Admin password updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
