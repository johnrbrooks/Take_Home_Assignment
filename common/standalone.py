from __future__ import annotations

from collections.abc import Callable

from common.config import Config
from common.context import AppContext
from common.errors import ProvisioningError
from common.ui import failure


def run_standalone(task: Callable[[AppContext], object]) -> None:
    """Allow a task module to run independently with `python -m tasks.<task>`."""
    context = AppContext(Config(interactive=True))
    try:
        task(context)
    except ProvisioningError as exc:
        failure(str(exc))
        raise SystemExit(1) from exc
