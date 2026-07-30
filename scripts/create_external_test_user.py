"""One-off: insert a single login-capable test user into whatever database
DATABASE_URL currently points at.

Built for testing this app against the external MySQL fork (see CLAUDE.md /
the external-DB test plan) - the fork's real `user` table has rows hashed
with the old app's passlib scheme, incompatible with this app's
werkzeug.security-based login, so nothing in it can log in as-is. This adds
one new row with a compatible hash; it never touches or removes any existing
row.

Reuses this app's own auth_service.create_user() rather than hand-rolling a
password hash. Does NOT run AUTO_INIT_DB/AUTO_SEED_DATA - it only ever adds
the one user row you ask for.

Usage:
    DATABASE_URL=mysql+pymysql://... python scripts/create_external_test_user.py \\
        --email test@example.com --password <password> [--name "External Test User"] [--write-access]
"""

import argparse

from transpower_conductor_noise_tool_2026.backend.app import create_app
from transpower_conductor_noise_tool_2026.backend.domain import auth_service
from transpower_conductor_noise_tool_2026.backend.persistence.repositories.user_repository import (
    UserRepository,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="External Test User")
    parser.add_argument("--write-access", action="store_true")
    args = parser.parse_args()

    app = create_app({"AUTO_INIT_DB": False, "AUTO_SEED_DATA": False})
    with app.app_context():
        repository = UserRepository()
        existing = repository.find_by_email(args.email)
        if existing:
            print(f"User {args.email!r} already exists (id={existing.id}) - not creating a duplicate.")
            return

        user = auth_service.create_user(
            name=args.name,
            email=args.email,
            password=args.password,
            write_access=args.write_access,
            repository=repository,
        )
        print(f"Created user {user.email!r} (id={user.id}, write_access={user.write_access}).")


if __name__ == "__main__":
    main()
