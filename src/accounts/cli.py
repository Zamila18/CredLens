"""Set up an organisation and its owner Credit Officer from the command line.

Purpose: a developer's shortcut. Companies normally register themselves at /register; this
    creates one from the server (for example for a pilot) with its owner Credit Officer.
    Everything after that (invitations, staff, shop assignments) is done in the application.
Owner role: D (full-stack).

    python -m src.accounts.cli create-org --id acme --name "Acme Finance" --environment pilot
    python -m src.accounts.cli create-owner --org acme --name "Rina Akter" --login rina@acme.example
    python -m src.accounts.cli setup-code --login rina@acme.example     (a new code, e.g. a reset)

`create-owner` and `setup-code` print a one-time setup code. Give it to the person: they open
/setup-password, enter their email or number, the code and a password of their choice. No
password is ever typed here or printed. Uses DATABASE_URL like the API.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy.orm import Session

from src.accounts import service
from src.config import get_database_url, load_config
from src.db.models import make_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    org = commands.add_parser("create-org", help="create a real (pilot or production) organisation")
    org.add_argument("--id", required=True)
    org.add_argument("--name", required=True)
    org.add_argument("--environment", choices=service.ORGANIZATION_ENVIRONMENTS, default="pilot")
    admin = commands.add_parser("create-owner", help="the owner Credit Officer of an organisation")
    admin.add_argument("--org", required=True)
    admin.add_argument("--name", required=True)
    admin.add_argument("--login", required=True, help="email address or mobile number")
    code = commands.add_parser("setup-code", help="a new one-time code to set a password")
    code.add_argument("--login", required=True)
    args = parser.parse_args(argv)

    config = load_config()
    engine = make_engine(get_database_url(config))
    with Session(engine) as session:
        try:
            if args.command == "create-org":
                service.create_organization(session, args.id, args.name, args.environment)
                session.commit()
                print(f"Organisation {args.id} created ({args.environment}).")
            elif args.command == "create-owner":
                user, _, setup = service.create_account(
                    session,
                    config,
                    args.org,
                    args.name,
                    args.login,
                    "credit_officer",
                    None,
                    is_owner=True,
                )
                session.commit()
                print(f"Owner {user.display_name} ({user.user_id}) created.")
                print(f"One-time setup code: {setup}")
                print("Valid for", config["auth"]["setup_code_hours"], "hours. Shown once.")
            else:
                credential = service.credential_for(session, args.login)
                if credential is None:
                    print("No account with that email or number.", file=sys.stderr)
                    return 1
                setup = service.issue_setup_code(session, config, credential.user_id, "cli")
                session.commit()
                print(f"One-time setup code: {setup}")
        except service.AccountError as error:
            print(error.message, file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
