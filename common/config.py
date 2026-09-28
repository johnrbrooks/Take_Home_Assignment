from __future__ import annotations

import getpass
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from common.errors import ConfigurationError
from common.models import SpaceDefinition


@dataclass(slots=True)
class Config:
    """
    Resolve configuration lazily, only when a selected task needs it.

    Resolution order:
      1. Runtime override already supplied to this Config instance.
      2. Environment variable / .env value.
      3. Interactive prompt.
      4. Optional displayed default if the user presses Enter.

    Values entered interactively are cached for the lifetime of the current
    CLI process, so later tasks in the same session reuse them.
    """

    overrides: Mapping[str, str | None] = field(default_factory=dict)
    interactive: bool = True
    _cache: dict[str, str] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        load_dotenv()

    def _resolve(
        self,
        key: str,
        *,
        prompt: str | None = None,
        default: str | None = None,
        secret: bool = False,
        required: bool = True,
    ) -> str | None:
        if key in self._cache:
            return self._cache[key]

        override = self.overrides.get(key)
        if override is not None and str(override).strip():
            value = str(override).strip()
            self._cache[key] = value
            return value

        env_value = os.getenv(key)
        if env_value and env_value.strip():
            value = env_value.strip()
            self._cache[key] = value
            return value

        if self.interactive and prompt:
            suffix = f" [{default}]" if default is not None else ""
            while True:
                raw = (
                    getpass.getpass(f"{prompt}{suffix}: ")
                    if secret
                    else input(f"{prompt}{suffix}: ")
                )
                value = raw.strip()

                if value:
                    self._cache[key] = value
                    return value

                if default is not None:
                    self._cache[key] = default
                    return default

                if not required:
                    return None

                print("A value is required.")

        # Non-interactive execution can still use a documented default.
        if default is not None:
            self._cache[key] = default
            return default

        if required:
            raise ConfigurationError(
                f"Missing required configuration value: {key}",
                "Set it as an environment variable/.env value or run interactively.",
            )

        return None

    @property
    def site_url(self) -> str:
        value = self._resolve(
            "ATLASSIAN_SITE_URL",
            prompt="Confluence site URL",
            default="https://oxalis-take-home.atlassian.net",
        )
        assert value is not None
        return value.rstrip("/")

    @property
    def confluence_email(self) -> str:
        value = self._resolve(
            "ATLASSIAN_USER_EMAIL",
            prompt="Admin Atlassian account email",
        )
        assert value is not None
        return value

    @property
    def confluence_api_token(self) -> str:
        value = self._resolve(
            "ATLASSIAN_API_TOKEN",
            prompt="Atlassian API token",
            secret=True,
        )
        assert value is not None
        return value

    @property
    def org_id(self) -> str:
        value = self._resolve(
            "ATLASSIAN_ORG_ID",
            prompt="Atlassian Organization ID",
        )
        assert value is not None
        return value

    @property
    def org_api_key(self) -> str:
        value = self._resolve(
            "ATLASSIAN_ORG_API_KEY",
            prompt="Atlassian Organization API key",
            secret=True,
        )
        assert value is not None
        return value

    @property
    def directory_id(self) -> str | None:
        return self._resolve("ATLASSIAN_DIRECTORY_ID", required=False)

    @property
    def users_csv_path(self) -> Path:
        # Conventional project input; no need to prompt on every task.
        raw = self._resolve("USERS_CSV_PATH", default="users.csv")
        assert raw is not None
        return Path(raw).expanduser()

    @property
    def group_name(self) -> str:
        # The assignment allows the implementer to choose the group name, so
        # do not silently manufacture one when no environment value exists.
        raw = self._resolve(
            "STANDARD_USERS_GROUP",
            prompt="Name for the standard-users group",
        )
        assert raw is not None
        return raw

    @property
    def collaborative_space(self) -> SpaceDefinition:
        # The exercise names the space, but the CLI intentionally allows the
        # operator to provide the effective name/key for reusable tooling.
        name = self._resolve(
            "COLLAB_SPACE_NAME",
            prompt="Collaborative space name",
        )
        key = self._resolve(
            "COLLAB_SPACE_KEY",
            prompt="Collaborative space key",
            default="COLLAB",
        )
        assert key and name
        return SpaceDefinition(
            key=key,
            name=name,
            description="Collaborative workspace provisioned by the take-home utility.",
        )

    @property
    def restricted_space(self) -> SpaceDefinition:
        name = self._resolve(
            "RESTRICT_SPACE_NAME",
            prompt="Restricted space name",
        )
        key = self._resolve(
            "RESTRICT_SPACE_KEY",
            prompt="Restricted space key",
            default="RESTRICT",
        )
        assert key and name
        return SpaceDefinition(
            key=key,
            name=name,
            description="Read-only workspace provisioned by the take-home utility.",
        )

    @property
    def restricted_read_only_role_name(self) -> str:
        raw = self._resolve(
            "RESTRICTED_READ_ONLY_ROLE_NAME",
            prompt="Read-only custom role name",
            default="Oxalis Read Only",
        )
        assert raw is not None
        return raw

    @property
    def restricted_page_title(self) -> str:
        raw = self._resolve(
            "RESTRICTED_PAGE_TITLE",
            prompt="Restricted page title",
            default="Confidential Collaboration Brief",
        )
        assert raw is not None
        return raw

    @property
    def restricted_page_user_key(self) -> str:
        raw = self._resolve(
            "RESTRICTED_PAGE_USER_KEY",
            prompt="Restricted page user key",
            default="user-2",
        )
        assert raw is not None
        return raw

    @property
    def image_path(self) -> Path:
        raw = self._resolve(
            "WORKSPACE_IMAGE_PATH",
            prompt="Workspace image path",
            default="assets/workspace-image.png",
        )
        assert raw is not None
        return Path(raw).expanduser()

    def set_runtime(self, key: str, value: str) -> None:
        self._cache[key] = value

    def describe(self) -> dict[str, str]:
        return {
            "Site URL": self.site_url,
            "Users CSV": str(self.users_csv_path),
            "Standard users group": self.group_name,
            "Collaborative space": (
                f"{self.collaborative_space.name} "
                f"[{self.collaborative_space.key}]"
            ),
            "Restricted space": (
                f"{self.restricted_space.name} "
                f"[{self.restricted_space.key}]"
            ),
            "Restricted page": self.restricted_page_title,
            "Restricted page user": self.restricted_page_user_key,
            "Image": str(self.image_path),
        }
