from __future__ import annotations

from typing import Any

import requests

from clients.base import BaseHttpClient
from common.errors import ConfigurationError


class AtlassianAdminClient(BaseHttpClient):
    """Client for Atlassian Organizations REST v2 directory/user lookup APIs."""

    def __init__(self, api_key: str) -> None:
        session = requests.Session()
        session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "oxalis-confluence-take-home/1.0",
            }
        )
        super().__init__("https://api.atlassian.com/admin", session)

    def get_directories(self, org_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/v2/orgs/{org_id}/directories",
            params={"limit": 100},
        )
        return response.json().get("data", [])

    def resolve_directory_id(
        self,
        org_id: str,
        configured_id: str | None = None,
        *,
        interactive: bool = True,
    ) -> str:
        if configured_id:
            return configured_id

        directories = self.get_directories(org_id)
        if not directories:
            raise ConfigurationError(
                "No Atlassian user directories were returned for the organization.",
                "Verify ATLASSIAN_ORG_ID and that the Organization API key can read directories.",
            )
        if len(directories) == 1:
            return str(directories[0]["directoryId"])

        if not interactive:
            raise ConfigurationError(
                "Multiple Atlassian directories were found but ATLASSIAN_DIRECTORY_ID is not set.",
                "Set ATLASSIAN_DIRECTORY_ID for non-interactive execution.",
            )

        print("\nMultiple Atlassian directories were found:")
        for index, directory in enumerate(directories, start=1):
            print(
                f"  {index}. {directory.get('name', '<unnamed>')} "
                f"({directory.get('directoryId')})"
            )

        while True:
            choice = input("Choose a directory number: ").strip()
            try:
                selected = int(choice) - 1
            except ValueError:
                selected = -1

            if 0 <= selected < len(directories):
                return str(directories[selected]["directoryId"])

            print("Please choose one of the listed directory numbers.")

    def search_user_by_email(
        self,
        org_id: str,
        directory_id: str,
        email: str,
    ) -> dict[str, Any] | None:
        """
        Resolve an organization-directory user by exact email address.

        The Organizations API remains useful for identity resolution even
        though organization-level invitation is not used by this utility.
        """
        response = self.request(
            "POST",
            f"/v2/orgs/{org_id}/directories/{directory_id}/users/search",
            json={"emails": [email], "limit": 10},
        )

        matches = response.json().get("data", [])
        exact = [
            user
            for user in matches
            if (user.get("email") or "").strip().lower() == email.lower()
        ]

        if not exact:
            return None

        if len(exact) > 1:
            raise ConfigurationError(
                f"Multiple Atlassian accounts unexpectedly matched the exact email {email}."
            )

        return exact[0]
