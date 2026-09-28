from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class UserRecord:
    user_key: str
    email: str
    account_id: str | None
    site_role: str
    collaborative_role: str

    def with_account_id(self, account_id: str) -> "UserRecord":
        return replace(self, account_id=account_id)


@dataclass(frozen=True, slots=True)
class SpaceDefinition:
    key: str
    name: str
    description: str


@dataclass(slots=True)
class TaskSummary:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    unresolved: int = 0
    failed: int = 0

    def ok(self) -> bool:
        return self.failed == 0
