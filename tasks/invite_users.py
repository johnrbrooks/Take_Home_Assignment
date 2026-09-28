from __future__ import annotations

from common.context import AppContext
from common.models import TaskSummary
from common.standalone import run_standalone
from common.ui import confirm, heading, info, success, warn


def run(ctx: AppContext) -> TaskSummary:
    heading("Invite / add standard users to Confluence")

    users = ctx.users.load()
    standards = [user for user in users if user.site_role == "standard"]
    emails = [user.email for user in standards]

    print("\nStandard users to submit for Confluence site access:")
    for user in standards:
        account_state = user.account_id or "accountId not resolved yet"
        print(f"  {user.user_key:<10} {user.email:<35} {account_state}")

    info(
        "This step intentionally submits all four standard-user emails directly to "
        "Confluence. Atlassian documents the invitation endpoint as asynchronous and "
        "states that addresses which already have site access are ignored."
    )

    if not confirm(
        "Submit Confluence site invitation request for these users?",
        ctx.assume_yes,
    ):
        warn("Invitation step cancelled by user.")
        return TaskSummary(unresolved=len(standards))

    # Do not call check-access-by-email first. Live tenant testing showed that
    # the experimental access-check response did not match the licensed-user
    # state visible in Atlassian Administration. The invite endpoint itself is
    # safe to submit repeatedly because Atlassian says it takes no action for
    # emails that already have site access.
    ctx.confluence.invite_users(emails)

    summary = TaskSummary(created=len(emails))
    for email in emails:
        success(f"Invitation request accepted for processing: {email}")

    print(
        f"\nSummary: invitation-requests-submitted={summary.created}, "
        f"failed={summary.failed}"
    )

    info(
        "Atlassian processes these invitations asynchronously. A successful HTTP "
        "response means the request was accepted, not that every accountId is already "
        "available. Re-run 'Resolve user account IDs' after provisioning completes."
    )

    return summary


if __name__ == "__main__":
    run_standalone(run)
