from __future__ import annotations

import time

from common.context import AppContext
from common.models import TaskSummary, UserRecord
from common.standalone import run_standalone
from common.ui import heading, info, success, warn


LOOKUP_ATTEMPTS = 4
LOOKUP_DELAY_SECONDS = 3


def run(ctx: AppContext, *, retry_missing: bool = False) -> TaskSummary:
    heading("Resolve Atlassian account IDs")
    users = ctx.users.load()
    summary = TaskSummary()

    current_user = ctx.confluence.get_current_user()
    current_account_id = current_user.get("accountId")
    current_email = ctx.config.confluence_email.strip().lower()

    # First satisfy anything that can be resolved without the Organizations API.
    staged: list[UserRecord] = []
    unresolved_for_org: list[UserRecord] = []
    for user in users:
        if user.account_id:
            success(f"{user.user_key}: already resolved ({user.account_id})")
            staged.append(user)
            summary.skipped += 1
            continue
        if user.email == current_email and current_account_id:
            resolved = user.with_account_id(str(current_account_id))
            staged.append(resolved)
            success(f"{user.user_key}: resolved from authenticated Confluence account")
            summary.updated += 1
            continue
        staged.append(user)
        unresolved_for_org.append(user)

    if not unresolved_for_org:
        ctx.users.save(staged)
        info(f"Updated {ctx.config.users_csv_path} atomically")
        return summary

    directory_id = ctx.admin.resolve_directory_id(
        ctx.config.org_id,
        ctx.config.directory_id,
        interactive=ctx.config.interactive,
    )
    info(f"Using Atlassian directory {directory_id}")

    resolved_by_key: dict[str, str] = {}
    for user in unresolved_for_org:
        attempts = LOOKUP_ATTEMPTS if retry_missing else 1
        match = None
        for attempt in range(1, attempts + 1):
            match = ctx.admin.search_user_by_email(
                ctx.config.org_id,
                directory_id,
                user.email,
            )
            if match:
                break
            if attempt < attempts:
                info(
                    f"{user.user_key}: not visible yet; retrying in "
                    f"{LOOKUP_DELAY_SECONDS}s ({attempt}/{attempts})"
                )
                time.sleep(LOOKUP_DELAY_SECONDS)

        account_id = str(match.get("accountId")) if match and match.get("accountId") else None
        if account_id:
            resolved_by_key[user.user_key] = account_id
            success(f"{user.user_key}: {account_id}")
            summary.updated += 1
        else:
            warn(f"{user.user_key}: no account found yet for {user.email}")
            summary.unresolved += 1

    output: list[UserRecord] = []
    for user in staged:
        account_id = resolved_by_key.get(user.user_key)
        output.append(user.with_account_id(account_id) if account_id else user)

    ctx.users.save(output)
    info(f"Updated {ctx.config.users_csv_path} atomically")
    print(
        f"\nResolved/updated: {summary.updated} | Already present: {summary.skipped} | "
        f"Unresolved: {summary.unresolved}"
    )
    return summary


if __name__ == "__main__":
    run_standalone(run)
