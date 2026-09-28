from __future__ import annotations

from dataclasses import dataclass, field

from clients.admin import AtlassianAdminClient
from clients.confluence import ConfluenceClient
from common.config import Config
from common.csv_store import CsvUserStore


@dataclass(slots=True)
class AppContext:
    config: Config
    assume_yes: bool = False
    _confluence: ConfluenceClient | None = field(default=None, init=False)
    _admin: AtlassianAdminClient | None = field(default=None, init=False)
    _users: CsvUserStore | None = field(default=None, init=False)

    @property
    def confluence(self) -> ConfluenceClient:
        if self._confluence is None:
            self._confluence = ConfluenceClient(
                self.config.site_url,
                self.config.confluence_email,
                self.config.confluence_api_token,
            )
        return self._confluence

    @property
    def admin(self) -> AtlassianAdminClient:
        if self._admin is None:
            self._admin = AtlassianAdminClient(self.config.org_api_key)
        return self._admin

    @property
    def users(self) -> CsvUserStore:
        if self._users is None:
            self._users = CsvUserStore(self.config.users_csv_path)
        return self._users
