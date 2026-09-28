from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from common.errors import CsvValidationError
from common.models import UserRecord


class CsvUserStore:
    REQUIRED_COLUMNS = {
        "user_key",
        "email",
        "site_role",
        "collaborative_role",
    }
    OUTPUT_COLUMNS = [
        "user_key",
        "email",
        "account_id",
        "site_role",
        "collaborative_role",
    ]

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[UserRecord]:
        if not self.path.exists():
            raise CsvValidationError(
                f"Users CSV does not exist: {self.path}",
                "Create/populate users.csv before running user-related tasks.",
            )

        with self.path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise CsvValidationError("users.csv has no header row.")

            missing = self.REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing:
                raise CsvValidationError(
                    "users.csv is missing required column(s): " + ", ".join(sorted(missing))
                )

            users: list[UserRecord] = []
            for row_number, row in enumerate(reader, start=2):
                users.append(
                    UserRecord(
                        user_key=(row.get("user_key") or "").strip(),
                        email=(row.get("email") or "").strip().lower(),
                        account_id=(row.get("account_id") or "").strip() or None,
                        site_role=(row.get("site_role") or "").strip().lower(),
                        collaborative_role=(row.get("collaborative_role") or "").strip().lower(),
                    )
                )
                if not users[-1].user_key or not users[-1].email:
                    raise CsvValidationError(
                        f"Row {row_number} is missing user_key or email.",
                        "Populate all five email addresses before running the utility.",
                    )

        self._validate_assignment_shape(users)
        return users

    def save(self, users: list[UserRecord]) -> None:
        """Atomically rewrite the CSV so a failed write cannot corrupt the source file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            dir=str(self.path.parent),
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self.OUTPUT_COLUMNS)
                writer.writeheader()
                for user in users:
                    writer.writerow(
                        {
                            "user_key": user.user_key,
                            "email": user.email,
                            "account_id": user.account_id or "",
                            "site_role": user.site_role,
                            "collaborative_role": user.collaborative_role,
                        }
                    )
            os.replace(temp_path, self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_assignment_shape(users: list[UserRecord]) -> None:
        if len(users) != 5:
            raise CsvValidationError(f"Expected exactly 5 users; found {len(users)}.")

        admins = [u for u in users if u.site_role == "admin"]
        standards = [u for u in users if u.site_role == "standard"]
        space_admins = [u for u in standards if u.collaborative_role == "space_admin"]

        if len(admins) != 1:
            raise CsvValidationError(f"Expected exactly 1 admin row; found {len(admins)}.")
        if len(standards) != 4:
            raise CsvValidationError(f"Expected exactly 4 standard-user rows; found {len(standards)}.")
        if len(space_admins) != 1:
            raise CsvValidationError(
                "Exactly one standard user must have collaborative_role=space_admin."
            )

        allowed_site_roles = {"admin", "standard"}
        invalid_site = {u.site_role for u in users} - allowed_site_roles
        if invalid_site:
            raise CsvValidationError(f"Unsupported site_role values: {sorted(invalid_site)}")

        allowed_collab_roles = {"site_admin", "space_admin", "editor"}
        invalid_collab = {u.collaborative_role for u in users} - allowed_collab_roles
        if invalid_collab:
            raise CsvValidationError(
                f"Unsupported collaborative_role values: {sorted(invalid_collab)}"
            )

        emails = [u.email for u in users]
        duplicate_emails = sorted({email for email in emails if emails.count(email) > 1})
        if duplicate_emails:
            raise CsvValidationError(
                "Duplicate email address(es): " + ", ".join(duplicate_emails)
            )

        keys = [u.user_key for u in users]
        duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
        if duplicate_keys:
            raise CsvValidationError("Duplicate user_key value(s): " + ", ".join(duplicate_keys))
