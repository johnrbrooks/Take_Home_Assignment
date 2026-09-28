from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from common.csv_store import CsvUserStore


class CsvUserStoreTests(unittest.TestCase):
    def _make_csv(self, directory: Path) -> Path:
        path = directory / "users.csv"
        path.write_text(
            "user_key,email,account_id,site_role,collaborative_role\n"
            "admin-user,admin@example.com,,admin,site_admin\n"
            "user-1,u1@example.com,,standard,space_admin\n"
            "user-2,u2@example.com,,standard,editor\n"
            "user-3,u3@example.com,,standard,editor\n"
            "user-4,u4@example.com,,standard,editor\n",
            encoding="utf-8",
        )
        return path

    def test_load_and_atomic_save_account_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self._make_csv(Path(temp))
            store = CsvUserStore(path)
            users = store.load()
            users[1] = users[1].with_account_id("acct-1")
            store.save(users)
            reloaded = store.load()
            self.assertEqual("acct-1", reloaded[1].account_id)
            self.assertEqual(5, len(reloaded))

    def test_output_contains_account_id_column(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = self._make_csv(Path(temp))
            store = CsvUserStore(path)
            store.save(store.load())
            with path.open(newline="", encoding="utf-8") as handle:
                headers = csv.DictReader(handle).fieldnames
            self.assertIn("account_id", headers or [])


if __name__ == "__main__":
    unittest.main()
