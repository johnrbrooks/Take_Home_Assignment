from __future__ import annotations

from html import escape

from common.context import AppContext
from common.errors import (
    ConfigurationError,
    ResourceNotFoundError,
    WorkflowPausedError,
)
from common.models import TaskSummary
from common.standalone import run_standalone
from common.ui import heading, info, success, warn


def _select_restricted_user(
    ctx: AppContext,
    requested_key: str | None = None,
):
    users = ctx.users.load()
    standards = [
        user
        for user in users
        if user.site_role == "standard"
    ]

    if requested_key:
        key = requested_key
    elif ctx.assume_yes:
        key = ctx.config.restricted_page_user_key
    else:
        print(
            "\nChoose the standard user who should be able to read "
            "the restricted page:"
        )
        for index, user in enumerate(standards, start=1):
            print(
                f"  {index}. {user.user_key} "
                f"({user.email})"
            )

        default_key = ctx.config.restricted_page_user_key
        choice = input(
            f"User key or number [{default_key}]: "
        ).strip()

        if not choice:
            key = default_key
        elif (
            choice.isdigit()
            and 1 <= int(choice) <= len(standards)
        ):
            key = standards[int(choice) - 1].user_key
        else:
            key = choice

    matching = [
        user
        for user in standards
        if user.user_key == key
    ]

    if len(matching) != 1:
        raise ConfigurationError(
            f"Unknown standard user_key for page restriction: {key}"
        )

    if not matching[0].account_id:
        raise WorkflowPausedError(
            f"{key} does not yet have a resolved accountId.",
            "Run resolve-users before creating page restrictions.",
        )

    return matching[0]


def _body_without_image() -> str:
    return (
        "<h1>Collaboration Brief</h1>"
        "<p>This page demonstrates automated Confluence Cloud "
        "content provisioning, attachment handling, and page-level "
        "access restrictions.</p>"
        "<p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
        "Integer posuere erat a ante venenatis dapibus posuere velit "
        "aliquet.</p>"
    )


def _body_with_image(filename: str) -> str:
    safe_filename = escape(filename, quote=True)
    return (
        _body_without_image()
        + "<h2>Workspace Overview</h2>"
        + (
            '<ac:image ac:alt="Workspace overview">'
            f'<ri:attachment ri:filename="{safe_filename}" />'
            "</ac:image>"
        )
    )


def _restriction_readers(
    ctx: AppContext,
    *,
    selected_user,
) -> list[tuple[str, str]]:
    """
    Build the ordered set of users that must remain in the page read
    restriction.

    Confluence will reject a restriction update that removes the requesting
    user from READ access. The API-authenticated user is therefore added first,
    followed by the exercise administrator (if different), then the selected
    standard user.

    The take-home's "only one specific user" requirement is interpreted as
    "only one of the four standard users"; the administrator must retain access
    so the provisioning account does not lock itself out.
    """
    users = ctx.users.load()
    admin = next(
        user
        for user in users
        if user.site_role == "admin"
    )

    current = ctx.confluence.get_current_user()
    current_account_id = str(
        current.get("accountId") or ""
    ).strip()

    if not current_account_id:
        raise ConfigurationError(
            "Confluence did not return an accountId for the "
            "authenticated API user."
        )

    readers: list[tuple[str, str]] = [
        (
            current_account_id,
            str(
                current.get("displayName")
                or "authenticated API user"
            ),
        )
    ]

    if (
        admin.account_id
        and admin.account_id != current_account_id
    ):
        readers.append(
            (admin.account_id, admin.user_key)
        )

    assert selected_user.account_id is not None
    if all(
        account_id != selected_user.account_id
        for account_id, _ in readers
    ):
        readers.append(
            (
                selected_user.account_id,
                selected_user.user_key,
            )
        )

    return readers


def run(
    ctx: AppContext,
    *,
    restricted_user_key: str | None = None,
) -> TaskSummary:
    heading("Create restricted page and embedded image")
    summary = TaskSummary()

    selected_user = _select_restricted_user(
        ctx,
        restricted_user_key,
    )
    ctx.config.set_runtime(
        "RESTRICTED_PAGE_USER_KEY",
        selected_user.user_key,
    )
    assert selected_user.account_id is not None

    info(
        f"Restricted page reader: "
        f"{selected_user.user_key} ({selected_user.email})"
    )
    info(
        "The selected user will be the only standard user granted "
        "page-level read access. The authenticated administrator is "
        "also retained because Confluence does not allow a restriction "
        "change to evict the requesting user."
    )

    image_path = ctx.config.image_path
    if not image_path.exists():
        raise ConfigurationError(
            f"Embedded image file does not exist: {image_path}",
            "Use WORKSPACE_IMAGE_PATH or place the provided image "
            "under assets/.",
        )

    # The assignment requires the page to be created in the first space:
    # Collaborative Workspace. "Restricted" here refers to the page-level
    # restriction, not the Restricted Workspace.
    space_def = ctx.config.collaborative_space
    space = ctx.confluence.get_space_by_key(
        space_def.key
    )
    if not space:
        raise ResourceNotFoundError(
            f"Collaborative space does not exist: "
            f"{space_def.key}",
            "Run create-spaces first.",
        )

    title = ctx.config.restricted_page_title
    page = ctx.confluence.find_page(
        str(space["id"]),
        title,
    )

    if page is None:
        page = ctx.confluence.create_page(
            str(space["id"]),
            title,
            _body_without_image(),
        )
        success(
            f"Created page: {title} "
            f"(id={page['id']})"
        )
        summary.created += 1
    else:
        success(
            f"Page already exists: {title} "
            f"(id={page['id']})"
        )
        summary.skipped += 1

    page_id = str(page["id"])

    ctx.confluence.upload_or_update_attachment(
        page_id,
        image_path,
    )
    success(
        f"Uploaded/updated attachment: "
        f"{image_path.name}"
    )
    summary.updated += 1

    current_page = ctx.confluence.get_page(page_id)
    current_version = int(
        (current_page.get("version") or {}).get(
            "number",
            1,
        )
    )

    ctx.confluence.update_page(
        page_id,
        title,
        _body_with_image(image_path.name),
        current_version + 1,
    )
    success(
        "Updated page body with embedded attachment"
    )
    summary.updated += 1

    readers = _restriction_readers(
        ctx,
        selected_user=selected_user,
    )

    # Reset assignment-owned restrictions, then add the authenticated user
    # FIRST. Once the first READ restriction exists, Confluence immediately
    # evaluates whether the requesting user would be evicted.
    ctx.confluence.clear_content_restrictions(
        page_id
    )

    for account_id, label in readers:
        ctx.confluence.add_user_read_restriction(
            page_id,
            account_id,
        )
        success(
            f"Added page read restriction member: "
            f"{label}"
        )

    standard_reader_count = sum(
        1
        for _, label in readers
        if label == selected_user.user_key
    )

    if standard_reader_count != 1:
        warn(
            "Unexpected page restriction state: the selected "
            "standard user was not added exactly once."
        )

    success(
        f"Applied page restriction: "
        f"{selected_user.user_key} is the only standard user "
        "with page-level read access; administrator access retained."
    )
    summary.updated += 1

    return summary


if __name__ == "__main__":
    run_standalone(run)
