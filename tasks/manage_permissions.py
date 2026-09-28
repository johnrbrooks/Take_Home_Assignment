from __future__ import annotations

from typing import Any

from common.context import AppContext
from common.errors import (
    ConfigurationError,
    ResourceNotFoundError,
    WorkflowPausedError,
)
from common.models import TaskSummary
from common.standalone import run_standalone
from common.ui import heading, info, success


SYSTEM_ADMIN_ROLE = "Admin"
SYSTEM_COLLABORATOR_ROLE = "Collaborator"
VIEW_CONTENT_PERMISSION = "View content"


def _merge(target: TaskSummary, source: TaskSummary) -> None:
    target.created += source.created
    target.updated += source.updated
    target.skipped += source.skipped
    target.unresolved += source.unresolved
    target.failed += source.failed


def _assignment_for(
    assignments: list[dict[str, Any]],
    *,
    principal_type: str,
    principal_id: str,
) -> dict[str, Any] | None:
    expected_type = principal_type.casefold()

    for assignment in assignments:
        principal = assignment.get("principal") or {}
        actual_type = str(
            principal.get("principalType") or principal.get("type") or ""
        ).casefold()
        actual_id = str(
            principal.get("principalId") or principal.get("id") or ""
        )

        if actual_type == expected_type and actual_id == principal_id:
            return assignment

    return None


def _ensure_role_assignment(
    ctx: AppContext,
    *,
    space: dict[str, Any],
    principal_type: str,
    principal_id: str,
    role: dict[str, Any],
    label: str,
) -> TaskSummary:
    summary = TaskSummary()
    space_id = str(space["id"])
    expected_role_id = str(role["id"])

    assignments = ctx.confluence.get_space_role_assignments(space_id)
    current = _assignment_for(
        assignments,
        principal_type=principal_type,
        principal_id=principal_id,
    )

    if current and str(current.get("roleId")) == expected_role_id:
        success(
            f"Already correct: {label} -> {role.get('name')} "
            f"in {space.get('name') or space.get('key')}"
        )
        summary.skipped += 1
        return summary

    ctx.confluence.set_space_role_assignments(
        space_id,
        [
            {
                "principal": {
                    "principalType": principal_type.upper(),
                    "principalId": principal_id,
                },
                "roleId": expected_role_id,
            }
        ],
    )

    action = "Updated" if current else "Assigned"
    success(
        f"{action}: {label} -> {role.get('name')} "
        f"in {space.get('name') or space.get('key')}"
    )
    summary.updated += 1
    return summary


def _find_required_role(
    ctx: AppContext,
    *,
    name: str,
    space_id: str,
) -> dict[str, Any]:
    role = ctx.confluence.find_space_role_by_name(
        name,
        space_id=space_id,
    )
    if role:
        return role

    # Some tenants expose system roles globally rather than through a
    # space-filtered lookup. Fall back to the global role collection.
    role = ctx.confluence.find_space_role_by_name(name)
    if role:
        return role

    raise ResourceNotFoundError(
        f"Confluence space role not found: {name}",
        "Inspect Confluence Settings -> Permissions -> Space roles.",
    )


def _ensure_read_only_role(ctx: AppContext) -> dict[str, Any]:
    """
    Ensure a genuinely view-only custom role exists.

    Confluence's default Viewer role also permits comments. The assignment
    explicitly asks for read-only access, so this utility creates/reuses a
    custom role containing View content only (plus any permission IDs that
    Atlassian marks as required dependencies).
    """
    role_name = ctx.config.restricted_read_only_role_name

    existing = ctx.confluence.find_space_role_by_name(role_name)
    if existing:
        return existing

    available = ctx.confluence.get_available_space_permissions()

    view_permission = next(
        (
            permission
            for permission in available
            if (permission.get("displayName") or "").casefold()
            == VIEW_CONTENT_PERMISSION.casefold()
        ),
        None,
    )

    if not view_permission:
        raise ConfigurationError(
            f"Could not locate the '{VIEW_CONTENT_PERMISSION}' RBAC permission.",
            "Check GET /wiki/api/v2/space-permissions against this tenant.",
        )

    permission_ids = {
        str(view_permission["id"]),
        *[
            str(permission_id)
            for permission_id in view_permission.get(
                "requiredPermissionIds",
                [],
            )
        ],
    }

    created = ctx.confluence.create_space_role(
        name=role_name,
        description=(
            "View-only role created by the Oxalis take-home provisioning "
            "utility to satisfy the Restricted Workspace requirement."
        ),
        permission_ids=sorted(permission_ids),
    )
    success(f"Created custom Confluence role: {role_name}")
    return created


def _run_rbac(
    ctx: AppContext,
    *,
    target: str,
    users: list,
    group: dict[str, Any],
) -> TaskSummary:
    summary = TaskSummary()

    standards = [
        user
        for user in users
        if user.site_role == "standard"
    ]
    admin_user = next(
        user
        for user in users
        if user.site_role == "admin"
    )
    space_admin = next(
        user
        for user in standards
        if user.collaborative_role == "space_admin"
    )

    assert admin_user.account_id is not None
    assert space_admin.account_id is not None

    group_id = str(group["id"])

    if target in {"all", "collaborative"}:
        collab_def = ctx.config.collaborative_space
        collab = ctx.confluence.get_space_by_key(collab_def.key)

        if not collab:
            raise ResourceNotFoundError(
                f"Space not found: {collab_def.key}",
                "Run create-spaces first using the same Collaborative space key.",
            )

        info(
            f"Reconciling {collab_def.name} "
            f"[{collab_def.key}] using Confluence RBAC"
        )

        collaborator_role = _find_required_role(
            ctx,
            name=SYSTEM_COLLABORATOR_ROLE,
            space_id=str(collab["id"]),
        )
        admin_role = _find_required_role(
            ctx,
            name=SYSTEM_ADMIN_ROLE,
            space_id=str(collab["id"]),
        )

        # All four standard users belong to the custom group. Giving that group
        # Collaborator provides the requested read/write behavior. The one
        # designated standard user receives Admin individually; Confluence
        # permissions are additive, so their Admin role supersets the group's
        # Collaborator access.
        _merge(
            summary,
            _ensure_role_assignment(
                ctx,
                space=collab,
                principal_type="GROUP",
                principal_id=group_id,
                role=collaborator_role,
                label=ctx.config.group_name,
            ),
        )
        _merge(
            summary,
            _ensure_role_assignment(
                ctx,
                space=collab,
                principal_type="USER",
                principal_id=space_admin.account_id,
                role=admin_role,
                label=space_admin.user_key,
            ),
        )

    if target in {"all", "restricted"}:
        restricted_def = ctx.config.restricted_space
        restricted = ctx.confluence.get_space_by_key(
            restricted_def.key
        )

        if not restricted:
            raise ResourceNotFoundError(
                f"Space not found: {restricted_def.key}",
                "Run create-spaces first using the same Restricted space key.",
            )

        info(
            f"Reconciling {restricted_def.name} "
            f"[{restricted_def.key}] using Confluence RBAC"
        )

        read_only_role = _ensure_read_only_role(ctx)
        admin_role = _find_required_role(
            ctx,
            name=SYSTEM_ADMIN_ROLE,
            space_id=str(restricted["id"]),
        )

        # The standard-user group gets a true view-only custom role. The site
        # administrator is explicitly assigned Admin to satisfy the requirement
        # that only the site administrator has space-administrator access among
        # the five exercise users.
        _merge(
            summary,
            _ensure_role_assignment(
                ctx,
                space=restricted,
                principal_type="GROUP",
                principal_id=group_id,
                role=read_only_role,
                label=ctx.config.group_name,
            ),
        )
        _merge(
            summary,
            _ensure_role_assignment(
                ctx,
                space=restricted,
                principal_type="USER",
                principal_id=admin_user.account_id,
                role=admin_role,
                label=admin_user.user_key,
            ),
        )

    return summary


# ---------------- Legacy compatibility ----------------

COLLAB_GROUP_PERMISSIONS = {
    ("read", "space"),
    ("create", "page"),
    ("create", "comment"),
    ("create", "attachment"),
}
RESTRICTED_GROUP_PERMISSIONS = {
    ("read", "space"),
}
SPACE_ADMIN_PERMISSIONS = {
    ("read", "space"),
    ("administer", "space"),
}


def _permission_tuple(permission: dict) -> tuple[str, str]:
    operation = permission.get("operation") or {}
    key = str(operation.get("key") or "").casefold()
    target = str(
        operation.get("targetType")
        or operation.get("target")
        or ""
    ).casefold()
    return key, target


def _principal_matches(
    permission: dict,
    principal_type: str,
    identifier: str,
) -> bool:
    principal = permission.get("principal") or permission.get("subject") or {}
    p_type = str(
        principal.get("type")
        or principal.get("principalType")
        or ""
    ).casefold()
    p_id = str(
        principal.get("id")
        or principal.get("identifier")
        or principal.get("principalId")
        or ""
    )
    return p_type == principal_type.casefold() and p_id == identifier


def _add_order(permission: tuple[str, str]) -> tuple[int, str, str]:
    key, target = permission
    priority = 0 if (key, target) == ("read", "space") else 1
    return priority, key, target


def _remove_order(permission: tuple[str, str]) -> tuple[int, str, str]:
    key, target = permission
    priority = 1 if (key, target) == ("read", "space") else 0
    return priority, key, target


def _reconcile_legacy_subject(
    ctx: AppContext,
    *,
    space: dict,
    principal_type: str,
    identifier: str,
    expected: set[tuple[str, str]],
    label: str,
) -> TaskSummary:
    summary = TaskSummary()
    permissions = ctx.confluence.get_space_permissions(str(space["id"]))
    direct = [
        permission
        for permission in permissions
        if _principal_matches(permission, principal_type, identifier)
    ]
    current = {_permission_tuple(permission) for permission in direct}

    extras = current - expected
    missing = expected - current

    direct_extras = [
        permission
        for permission in direct
        if _permission_tuple(permission) in extras
        and permission.get("id")
    ]
    direct_extras.sort(
        key=lambda permission: _remove_order(_permission_tuple(permission))
    )

    for permission in direct_extras:
        p_tuple = _permission_tuple(permission)
        ctx.confluence.remove_space_permission(
            space["key"],
            str(permission["id"]),
        )
        info(
            f"Removed extra {label} permission: "
            f"{p_tuple[0]}/{p_tuple[1]}"
        )
        summary.updated += 1

    for operation_key, permission_target in sorted(
        missing,
        key=_add_order,
    ):
        ctx.confluence.add_space_permission(
            space["key"],
            principal_type,
            identifier,
            operation_key,
            permission_target,
        )
        success(
            f"Added {label} permission: "
            f"{operation_key}/{permission_target}"
        )
        summary.updated += 1

    return summary


def _run_legacy(
    ctx: AppContext,
    *,
    target: str,
    users: list,
    group: dict[str, Any],
) -> TaskSummary:
    summary = TaskSummary()
    standards = [
        user
        for user in users
        if user.site_role == "standard"
    ]
    group_id = str(group["id"])

    if target in {"all", "collaborative"}:
        collab_def = ctx.config.collaborative_space
        collab = ctx.confluence.get_space_by_key(collab_def.key)
        if not collab:
            raise ResourceNotFoundError(f"Space not found: {collab_def.key}")

        _merge(
            summary,
            _reconcile_legacy_subject(
                ctx,
                space=collab,
                principal_type="group",
                identifier=group_id,
                expected=COLLAB_GROUP_PERMISSIONS,
                label=ctx.config.group_name,
            ),
        )

        space_admin = next(
            user
            for user in standards
            if user.collaborative_role == "space_admin"
        )
        assert space_admin.account_id is not None
        _merge(
            summary,
            _reconcile_legacy_subject(
                ctx,
                space=collab,
                principal_type="user",
                identifier=space_admin.account_id,
                expected=SPACE_ADMIN_PERMISSIONS,
                label=space_admin.user_key,
            ),
        )

    if target in {"all", "restricted"}:
        restricted_def = ctx.config.restricted_space
        restricted = ctx.confluence.get_space_by_key(restricted_def.key)
        if not restricted:
            raise ResourceNotFoundError(
                f"Space not found: {restricted_def.key}"
            )

        _merge(
            summary,
            _reconcile_legacy_subject(
                ctx,
                space=restricted,
                principal_type="group",
                identifier=group_id,
                expected=RESTRICTED_GROUP_PERMISSIONS,
                label=ctx.config.group_name,
            ),
        )

    return summary


def run(ctx: AppContext, *, target: str = "all") -> TaskSummary:
    heading("Manage space permissions")

    users = ctx.users.load()
    if any(not user.account_id for user in users):
        raise WorkflowPausedError(
            "Space access configuration requires resolved accountIds for all five users.",
            "Run resolve-users after user provisioning completes.",
        )

    group_name = ctx.config.group_name
    group = ctx.confluence.find_group_by_name(group_name)
    if not group:
        raise ResourceNotFoundError(
            f"Required group does not exist: {group_name}",
            "Run manage-group first using the same group name.",
        )

    mode = ctx.confluence.get_space_role_mode()
    info(f"Confluence space access mode: {mode or '<unknown>'}")

    # New sites are role-enabled. The legacy granular permission writer is not
    # accepted in roles-only mode, which is why the prior implementation
    # returned InvalidRbacOperationException.
    if mode.casefold() == "pre_roles":
        return _run_legacy(
            ctx,
            target=target,
            users=users,
            group=group,
        )

    return _run_rbac(
        ctx,
        target=target,
        users=users,
        group=group,
    )


if __name__ == "__main__":
    run_standalone(run)
