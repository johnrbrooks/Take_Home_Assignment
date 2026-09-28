from __future__ import annotations

from collections.abc import Callable

from common.context import AppContext
from common.errors import ProvisioningError, WorkflowPausedError
from common.ui import failure, heading, pause, success, warn
from tasks import (
    create_content,
    create_spaces,
    invite_users,
    manage_group,
    manage_permissions,
    resolve_users,
    verify,
)


def _execute_with_retry(
    ctx: AppContext,
    name: str,
    action: Callable[[], object],
) -> object:
    while True:
        try:
            result = action()
            success(f"Completed: {name}")
            return result
        except ProvisioningError as exc:
            failure(f"{name} failed:\n{exc}")
            if ctx.assume_yes:
                raise

            choice = input("[R]etry this step / [S]top workflow: ").strip().lower()
            if choice in {"r", "retry"}:
                continue

            raise WorkflowPausedError(
                f"Workflow stopped after: {name}"
            ) from exc


def _step_pause(ctx: AppContext) -> None:
    if not ctx.assume_yes:
        pause("\nStep complete. Press Enter to continue to the next step...")


def run(
    ctx: AppContext,
    *,
    restricted_user_key: str | None = None,
) -> bool:
    heading("Run complete Confluence provisioning workflow")

    def resolve_after_invite() -> object:
        result = resolve_users.run(ctx, retry_missing=True)

        if result.unresolved:
            raise WorkflowPausedError(
                f"{result.unresolved} user(s) still do not have resolvable "
                "Atlassian accountIds.",
                "Confluence site invitations are asynchronous. Allow time for "
                "provisioning and, if Atlassian requires it for a new identity, "
                "complete the invited account setup. Then choose Retry.",
            )

        return result

    steps: list[tuple[str, Callable[[], object]]] = [
        ("Resolve existing account IDs", lambda: resolve_users.run(ctx)),
        (
            "Submit Confluence site invitations",
            lambda: invite_users.run(ctx),
        ),
        (
            "Resolve account IDs after invitations",
            resolve_after_invite,
        ),
        ("Create / reconcile group", lambda: manage_group.run(ctx)),
        ("Create spaces", lambda: create_spaces.run(ctx)),
        (
            "Apply space permissions",
            lambda: manage_permissions.run(ctx, target="all"),
        ),
        (
            "Create page, image, and page restriction",
            lambda: create_content.run(
                ctx,
                restricted_user_key=restricted_user_key,
            ),
        ),
        ("Verify configuration", lambda: verify.run(ctx)),
    ]

    for name, action in steps:
        result = _execute_with_retry(ctx, name, action)

        if name == "Verify configuration" and result is False:
            warn(
                "Provisioning completed, but one or more verification checks failed."
            )
            return False

        _step_pause(ctx)

    success("Complete provisioning workflow finished successfully.")
    return True


if __name__ == "__main__":
    from common.standalone import run_standalone

    run_standalone(run)
