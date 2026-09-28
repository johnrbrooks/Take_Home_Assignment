from __future__ import annotations

import argparse
import sys

from common.config import Config
from common.context import AppContext
from common.errors import ProvisioningError
from common.ui import failure, heading, pause
from tasks import (
    create_content,
    create_spaces,
    invite_users,
    manage_group,
    manage_permissions,
    resolve_users,
    run_all,
    verify,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactive/command-line Confluence provisioning utility for the Oxalis take-home exercise."
    )
    parser.add_argument("--site-url", help="Override ATLASSIAN_SITE_URL")
    parser.add_argument("--user-email", help="Override ATLASSIAN_USER_EMAIL")
    parser.add_argument("--api-token", help="Override ATLASSIAN_API_TOKEN (prefer env/prompt for secrets)")
    parser.add_argument("--org-id", help="Override ATLASSIAN_ORG_ID")
    parser.add_argument("--org-api-key", help="Override ATLASSIAN_ORG_API_KEY (prefer env/prompt for secrets)")
    parser.add_argument("--directory-id", help="Override ATLASSIAN_DIRECTORY_ID")
    parser.add_argument("--users-csv", help="Override USERS_CSV_PATH")
    parser.add_argument("--group-name", help="Override STANDARD_USERS_GROUP")
    parser.add_argument("--yes", action="store_true", help="Accept confirmations and skip run-all pauses")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Never prompt for missing configuration; fail instead",
    )

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("resolve-users", help="Resolve emails to accountIds and update users.csv")
    sub.add_parser("invite-users", help="Submit standard-user emails to the Confluence site invitation API")
    sub.add_parser("manage-group", help="Create/reconcile the standard-users group")
    sub.add_parser("create-spaces", help="Create the two assignment spaces if missing")

    permissions = sub.add_parser("permissions", help="Reconcile space permissions")
    permissions.add_argument(
        "--space",
        choices=("all", "collaborative", "restricted"),
        default="all",
        help="Which assignment space to reconcile",
    )

    content = sub.add_parser("create-content", help="Create/update the restricted page and image")
    content.add_argument("--restricted-user", help="user_key allowed to read the restricted page")

    sub.add_parser("verify", help="Verify users, group, spaces, permissions, and page restrictions")

    all_cmd = sub.add_parser("run-all", help="Run the complete provisioning workflow")
    all_cmd.add_argument("--restricted-user", help="user_key allowed to read the restricted page")

    sub.add_parser("show-config", help="Show non-secret effective configuration")
    return parser


def _overrides(args: argparse.Namespace) -> dict[str, str | None]:
    values = {
        "ATLASSIAN_SITE_URL": args.site_url,
        "ATLASSIAN_USER_EMAIL": args.user_email,
        "ATLASSIAN_API_TOKEN": args.api_token,
        "ATLASSIAN_ORG_ID": args.org_id,
        "ATLASSIAN_ORG_API_KEY": args.org_api_key,
        "ATLASSIAN_DIRECTORY_ID": args.directory_id,
        "USERS_CSV_PATH": args.users_csv,
        "STANDARD_USERS_GROUP": args.group_name,
    }
    restricted_user = getattr(args, "restricted_user", None)
    if restricted_user:
        values["RESTRICTED_PAGE_USER_KEY"] = restricted_user
    return values


def _show_config(ctx: AppContext) -> None:
    heading("Effective configuration")
    for key, value in ctx.config.describe().items():
        print(f"{key:24} {value}")


def _run_command(args: argparse.Namespace, ctx: AppContext) -> int:
    match args.command:
        case "resolve-users":
            resolve_users.run(ctx)
        case "invite-users":
            invite_users.run(ctx)
        case "manage-group":
            manage_group.run(ctx)
        case "create-spaces":
            create_spaces.run(ctx)
        case "permissions":
            manage_permissions.run(ctx, target=args.space)
        case "create-content":
            create_content.run(ctx, restricted_user_key=args.restricted_user)
        case "verify":
            return 0 if verify.run(ctx) else 2
        case "run-all":
            return 0 if run_all.run(ctx, restricted_user_key=args.restricted_user) else 2
        case "show-config":
            _show_config(ctx)
        case _:
            return interactive_menu(ctx)
    return 0


def _permission_menu(ctx: AppContext) -> None:
    print("\nSelect space permission target:")
    print("1. Both assignment spaces")
    print("2. Collaborative Workspace only")
    print("3. Restricted Workspace only")
    choice = input("Select an option [1]: ").strip() or "1"
    target = {"1": "all", "2": "collaborative", "3": "restricted"}.get(choice)
    if target is None:
        print("Invalid selection.")
        return
    manage_permissions.run(ctx, target=target)


def interactive_menu(ctx: AppContext) -> int:
    while True:
        heading("Oxalis Confluence Provisioning Utility")
        print(f"Site: {ctx.config.site_url}")
        print(f"Users file: {ctx.config.users_csv_path}")
        print(
            "\n"
            "1. Resolve user account IDs\n"
            "2. Invite / add users to Confluence\n"
            "3. Create / update standard-users group\n"
            "4. Create required spaces\n"
            "5. Configure space permissions\n"
            "6. Create restricted page and image\n"
            "7. Verify configuration\n"
            "8. Run complete provisioning workflow\n"
            "9. Show current configuration\n"
            "0. Exit"
        )
        choice = input("\nSelect an option: ").strip()

        try:
            if choice == "1":
                resolve_users.run(ctx)
            elif choice == "2":
                invite_users.run(ctx)
            elif choice == "3":
                manage_group.run(ctx)
            elif choice == "4":
                create_spaces.run(ctx)
            elif choice == "5":
                _permission_menu(ctx)
            elif choice == "6":
                create_content.run(ctx)
            elif choice == "7":
                verify.run(ctx)
            elif choice == "8":
                run_all.run(ctx)
            elif choice == "9":
                _show_config(ctx)
            elif choice == "0":
                return 0
            else:
                print("Invalid selection.")
                continue
        except ProvisioningError as exc:
            failure(str(exc))

        pause("\nPress Enter to return to the main menu...")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    interactive = not args.non_interactive
    config = Config(overrides=_overrides(args), interactive=interactive)
    ctx = AppContext(config=config, assume_yes=args.yes)

    try:
        return _run_command(args, ctx)
    except ProvisioningError as exc:
        failure(str(exc))
        return 1
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
