from __future__ import annotations

from common.context import AppContext
from common.errors import WorkflowPausedError
from common.models import TaskSummary
from common.standalone import run_standalone
from common.ui import heading, info, success


def run(ctx: AppContext) -> TaskSummary:
    heading("Create / reconcile standard-users group")
    users = ctx.users.load()
    standards = [u for u in users if u.site_role == "standard"]
    unresolved = [u for u in standards if not u.account_id]
    if unresolved:
        raise WorkflowPausedError(
            "Group membership cannot be configured until all four standard users have accountIds.",
            "Run resolve-users again after the Atlassian invitations/accounts have finished provisioning.",
        )

    group_name = ctx.config.group_name
    group = ctx.confluence.find_group_by_name(group_name)
    summary = TaskSummary()
    if group is None:
        group = ctx.confluence.create_group(group_name)
        success(f"Created group: {group_name}")
        summary.created += 1
    else:
        success(f"Group already exists: {group_name}")
        summary.skipped += 1

    group_id = str(group["id"])
    members = ctx.confluence.get_group_members(group_id)
    member_ids = {str(member.get("accountId")) for member in members if member.get("accountId")}

    for user in standards:
        assert user.account_id is not None
        if user.account_id in member_ids:
            success(f"Already a member: {user.user_key}")
            summary.skipped += 1
            continue
        ctx.confluence.add_group_member(group_id, user.account_id)
        success(f"Added to group: {user.user_key}")
        summary.updated += 1

    admin = next(u for u in users if u.site_role == "admin")
    if admin.account_id and admin.account_id in member_ids:
        ctx.confluence.remove_group_member(group_id, admin.account_id)
        success("Removed administrator from the standard-users group")
        summary.updated += 1

    info(f"Group ID: {group_id}")
    return summary


if __name__ == "__main__":
    run_standalone(run)
