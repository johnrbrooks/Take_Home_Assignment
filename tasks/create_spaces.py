from __future__ import annotations

from common.context import AppContext
from common.models import TaskSummary
from common.standalone import run_standalone
from common.ui import confirm, heading, success, warn


def run(ctx: AppContext) -> TaskSummary:
    heading("Create required Confluence spaces")
    spaces = [ctx.config.collaborative_space, ctx.config.restricted_space]
    summary = TaskSummary()

    print("The utility will ensure these private spaces exist:")
    for space in spaces:
        print(f"  - {space.name} [{space.key}]")

    if not confirm("Continue?", ctx.assume_yes):
        warn("Space creation cancelled by user.")
        return summary

    for definition in spaces:
        existing = ctx.confluence.get_space_by_key(definition.key)
        if existing:
            success(f"Already exists: {definition.name} [{definition.key}]")
            summary.skipped += 1
            continue

        created = ctx.confluence.create_private_space(definition.key, definition.name)
        success(
            f"Created private space: {definition.name} [{definition.key}] "
            f"(id={created.get('id', 'unknown')})"
        )
        summary.created += 1

    return summary


if __name__ == "__main__":
    run_standalone(run)
