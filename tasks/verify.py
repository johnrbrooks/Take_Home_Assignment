from __future__ import annotations

from typing import Any

from common.context import AppContext
from common.standalone import run_standalone
from common.ui import (
    failure,
    heading,
    info,
    success,
)
from tasks.manage_permissions import (
    SYSTEM_ADMIN_ROLE,
    SYSTEM_COLLABORATOR_ROLE,
)


def _assignment_for(
    assignments: list[dict[str, Any]],
    *,
    principal_type: str,
    principal_id: str,
) -> dict[str, Any] | None:
    for assignment in assignments:
        principal = assignment.get(
            "principal"
        ) or {}
        actual_type = str(
            principal.get("principalType")
            or principal.get("type")
            or ""
        ).casefold()
        actual_id = str(
            principal.get("principalId")
            or principal.get("id")
            or ""
        )

        if (
            actual_type == principal_type.casefold()
            and actual_id == principal_id
        ):
            return assignment

    return None


def run(ctx: AppContext) -> bool:
    heading("Verify take-home configuration")
    checks: list[
        tuple[str, bool, str | None]
    ] = []

    def record(
        label: str,
        passed: bool,
        detail: str | None = None,
    ) -> None:
        checks.append(
            (label, passed, detail)
        )
        if passed:
            success(label)
        else:
            failure(
                f"{label}"
                f"{': ' + detail if detail else ''}"
            )

    users = ctx.users.load()
    admin = next(
        user
        for user in users
        if user.site_role == "admin"
    )
    standards = [
        user
        for user in users
        if user.site_role == "standard"
    ]
    space_admin = next(
        user
        for user in standards
        if user.collaborative_role
        == "space_admin"
    )

    record(
        "All five users have resolved accountIds",
        all(user.account_id for user in users),
    )

    for user in users:
        if not user.account_id:
            record(
                f"{user.user_key} is visible "
                "to Confluence",
                False,
                "accountId unresolved",
            )
            continue

        confluence_user = (
            ctx.confluence.get_user(
                user.account_id
            )
        )
        record(
            f"{user.user_key} is visible "
            "to Confluence",
            confluence_user is not None,
        )

    group_name = ctx.config.group_name
    group = (
        ctx.confluence.find_group_by_name(
            group_name
        )
    )
    record(
        "Standard-users group exists",
        group is not None,
    )

    if group:
        members = (
            ctx.confluence.get_group_members(
                str(group["id"])
            )
        )
        member_ids = {
            str(member.get("accountId"))
            for member in members
            if member.get("accountId")
        }
        expected_ids = {
            user.account_id
            for user in standards
            if user.account_id
        }

        record(
            "Group contains all four "
            "standard users",
            (
                len(expected_ids) == 4
                and expected_ids <= member_ids
            ),
        )

        if admin.account_id:
            record(
                "Administrator is not in "
                "standard-users group",
                (
                    admin.account_id
                    not in member_ids
                ),
            )

    collab_def = (
        ctx.config.collaborative_space
    )
    restricted_def = (
        ctx.config.restricted_space
    )
    collab = (
        ctx.confluence.get_space_by_key(
            collab_def.key
        )
    )
    restricted = (
        ctx.confluence.get_space_by_key(
            restricted_def.key
        )
    )

    record(
        "Collaborative Workspace exists",
        collab is not None,
    )
    record(
        "Restricted Workspace exists",
        restricted is not None,
    )

    mode = (
        ctx.confluence.get_space_role_mode()
    )
    record(
        "Confluence space access mode "
        "was detected",
        bool(mode),
        mode or None,
    )

    if (
        mode.casefold() != "pre_roles"
        and group
        and collab
        and space_admin.account_id
    ):
        roles = {
            str(role["id"]): str(
                role.get("name") or ""
            )
            for role in (
                ctx.confluence.get_space_roles(
                    space_id=str(
                        collab["id"]
                    )
                )
            )
        }
        assignments = (
            ctx.confluence
            .get_space_role_assignments(
                str(collab["id"])
            )
        )

        group_assignment = (
            _assignment_for(
                assignments,
                principal_type="GROUP",
                principal_id=str(
                    group["id"]
                ),
            )
        )
        admin_assignment = (
            _assignment_for(
                assignments,
                principal_type="USER",
                principal_id=(
                    space_admin.account_id
                ),
            )
        )

        record(
            "Collaborative group has "
            "Collaborator role",
            bool(
                group_assignment
                and roles.get(
                    str(
                        group_assignment.get(
                            "roleId"
                        )
                    )
                )
                == SYSTEM_COLLABORATOR_ROLE
            ),
        )
        record(
            f"{space_admin.user_key} has "
            "Admin role in Collaborative "
            "Workspace",
            bool(
                admin_assignment
                and roles.get(
                    str(
                        admin_assignment.get(
                            "roleId"
                        )
                    )
                )
                == SYSTEM_ADMIN_ROLE
            ),
        )

    if (
        mode.casefold() != "pre_roles"
        and group
        and restricted
        and admin.account_id
    ):
        roles = {
            str(role["id"]): str(
                role.get("name") or ""
            )
            for role in (
                ctx.confluence.get_space_roles(
                    space_id=str(
                        restricted["id"]
                    )
                )
            )
        }
        assignments = (
            ctx.confluence
            .get_space_role_assignments(
                str(restricted["id"])
            )
        )

        group_assignment = (
            _assignment_for(
                assignments,
                principal_type="GROUP",
                principal_id=str(
                    group["id"]
                ),
            )
        )
        admin_assignment = (
            _assignment_for(
                assignments,
                principal_type="USER",
                principal_id=admin.account_id,
            )
        )

        read_only_role_name = (
            ctx.config
            .restricted_read_only_role_name
        )

        record(
            f"Restricted group has "
            f"{read_only_role_name} role",
            bool(
                group_assignment
                and roles.get(
                    str(
                        group_assignment.get(
                            "roleId"
                        )
                    )
                )
                == read_only_role_name
            ),
        )
        record(
            "Site administrator has Admin "
            "role in Restricted Workspace",
            bool(
                admin_assignment
                and roles.get(
                    str(
                        admin_assignment.get(
                            "roleId"
                        )
                    )
                )
                == SYSTEM_ADMIN_ROLE
            ),
        )

    if collab:
        page = ctx.confluence.find_page(
            str(collab["id"]),
            ctx.config.restricted_page_title,
        )
        record(
            "Required restricted page exists",
            page is not None,
        )

        if page:
            page_id = str(page["id"])
            attachments = (
                ctx.confluence
                .get_page_attachments(page_id)
            )
            attachment_names = {
                str(
                    attachment.get("title")
                )
                for attachment in attachments
            }

            record(
                "Required page has the "
                "embedded-image attachment",
                (
                    ctx.config.image_path.name
                    in attachment_names
                ),
            )

            selected = next(
                (
                    user
                    for user in standards
                    if user.user_key
                    == ctx.config
                    .restricted_page_user_key
                ),
                None,
            )

            if (
                selected
                and selected.account_id
            ):
                record(
                    "Read restriction explicitly "
                    f"includes {selected.user_key}",
                    (
                        ctx.confluence
                        .is_user_in_read_restriction(
                            page_id,
                            selected.account_id,
                        )
                    ),
                )

                # The exercise administrator must remain in the
                # restriction because Confluence prohibits the API caller
                # from evicting itself while applying READ restrictions.
                if admin.account_id:
                    record(
                        "Read restriction retains "
                        "the exercise administrator",
                        (
                            ctx.confluence
                            .is_user_in_read_restriction(
                                page_id,
                                admin.account_id,
                            )
                        ),
                    )

                # The requirement is enforced across the four standard
                # users: exactly the selected user can read the page.
                readable_standard_users = 0

                for user in standards:
                    if not user.account_id:
                        continue

                    should_read = (
                        user.user_key
                        == selected.user_key
                    )
                    actual = (
                        ctx.confluence
                        .check_content_permission(
                            page_id,
                            user.account_id,
                            "read",
                        )
                    )

                    if actual:
                        readable_standard_users += 1

                    record(
                        "Page effective read access "
                        f"for {user.user_key} "
                        f"is {should_read}",
                        actual == should_read,
                        (
                            f"actual={actual}"
                            if actual != should_read
                            else None
                        ),
                    )

                record(
                    "Exactly one standard user "
                    "can read the restricted page",
                    readable_standard_users == 1,
                    (
                        "readable standard users="
                        f"{readable_standard_users}"
                    ),
                )

                if admin.account_id:
                    admin_can_read = (
                        ctx.confluence
                        .check_content_permission(
                            page_id,
                            admin.account_id,
                            "read",
                        )
                    )
                    record(
                        "Administrator can still "
                        "read/manage the restricted "
                        "page",
                        admin_can_read,
                    )

    passed = sum(
        1
        for _, ok, _ in checks
        if ok
    )
    failed = len(checks) - passed

    print(
        f"\nRESULT: {passed} passed / "
        f"{failed} failed"
    )

    if failed:
        info(
            "Run the relevant task again, "
            "then re-run verification."
        )

    return failed == 0


if __name__ == "__main__":
    run_standalone(run)
