from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from clients.base import BaseHttpClient


class ConfluenceClient(BaseHttpClient):
    """Direct Confluence Cloud REST client using email + Atlassian API token."""

    def __init__(self, site_url: str, email: str, api_token: str) -> None:
        session = requests.Session()
        session.auth = (email, api_token)
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "oxalis-confluence-take-home/1.0",
            }
        )
        super().__init__(site_url, session)

    # ---------- User access ----------
    def get_current_user(self) -> dict[str, Any]:
        response = self.request("GET", "/wiki/rest/api/user/current")
        return response.json()

    def get_user(self, account_id: str) -> dict[str, Any] | None:
        response = self.request(
            "GET",
            "/wiki/rest/api/user",
            params={"accountId": account_id},
            allowed=(404,),
        )
        return None if response.status_code == 404 else response.json()

    def invite_users(self, emails: list[str]) -> dict[str, Any] | None:
        """Submit site invitations by email.

        Atlassian documents this endpoint as asynchronous and says it takes
        no action for addresses that already have site access. The caller
        therefore does not need a separate pre-check before submitting the
        request.
        """
        if not emails:
            return None
        response = self.request(
            "POST",
            "/wiki/api/v2/user/access/invite-by-email",
            json={"emails": emails},
        )
        try:
            return response.json()
        except ValueError:
            return None

    # ---------- Groups ----------
    def find_group_by_name(self, name: str) -> dict[str, Any] | None:
        response = self.request(
            "GET",
            "/wiki/rest/api/group/picker",
            params={"query": name, "limit": 100, "shouldReturnTotalSize": "true"},
        )
        for group in response.json().get("results", []):
            if (group.get("name") or "").casefold() == name.casefold():
                return group
        return None

    def create_group(self, name: str) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/wiki/rest/api/group",
            expected=(201,),
            json={"name": name},
        )
        return response.json()

    def get_group_members(self, group_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/wiki/rest/api/group/{group_id}/membersByGroupId",
            params={"limit": 200},
        )
        return response.json().get("results", [])

    def add_group_member(self, group_id: str, account_id: str) -> None:
        self.request(
            "POST",
            "/wiki/rest/api/group/userByGroupId",
            expected=(201,),
            params={"groupId": group_id},
            json={"accountId": account_id},
        )

    def remove_group_member(self, group_id: str, account_id: str) -> None:
        self.request(
            "DELETE",
            "/wiki/rest/api/group/userByGroupId",
            expected=(204,),
            params={"groupId": group_id, "accountId": account_id},
        )

    # ---------- Spaces ----------
    def get_space_by_key(self, key: str) -> dict[str, Any] | None:
        response = self.request(
            "GET",
            "/wiki/api/v2/spaces",
            params={"keys": key, "limit": 25},
        )
        for space in response.json().get("results", []):
            if (space.get("key") or "").casefold() == key.casefold():
                return space
        return None

    def create_private_space(self, key: str, name: str) -> dict[str, Any]:
        # v1 private-space creation is used intentionally so the new space starts
        # visible only to the creator. Explicit permissions are added afterward.
        response = self.request(
            "POST",
            "/wiki/rest/api/space/_private",
            json={"key": key, "name": name},
        )
        return response.json()

    def get_space_permissions(self, space_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/wiki/api/v2/spaces/{space_id}/permissions",
            params={"limit": 250},
        )
        return response.json().get("results", [])

    def add_space_permission(
        self,
        space_key: str,
        subject_type: str,
        identifier: str,
        operation_key: str,
        target: str,
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            f"/wiki/rest/api/space/{space_key}/permission",
            json={
                "subject": {"type": subject_type, "identifier": identifier},
                "operation": {"key": operation_key, "target": target},
            },
        )
        return response.json()

    def remove_space_permission(self, space_key: str, permission_id: str) -> None:
        self.request(
            "DELETE",
            f"/wiki/rest/api/space/{space_key}/permission/{permission_id}",
            expected=(204,),
        )


    # ---------- Space roles / RBAC ----------
    def get_space_role_mode(self) -> str:
        """
        Return the tenant's Confluence space access mode.

        New Confluence sites use role-based access. Older sites can report
        PRE_ROLES. For any role-enabled mode, this utility uses the v2 role
        assignment APIs rather than the legacy granular-permission write API.
        """
        response = self.request(
            "GET",
            "/wiki/api/v2/space-role-mode",
        )
        return str(response.json().get("mode") or "")

    def get_space_roles(
        self,
        *,
        space_id: str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": 100}
        if space_id:
            params["space-id"] = space_id

        response = self.request(
            "GET",
            "/wiki/api/v2/space-roles",
            params=params,
        )
        return response.json().get("results", [])

    def find_space_role_by_name(
        self,
        name: str,
        *,
        space_id: str | None = None,
    ) -> dict[str, Any] | None:
        for role in self.get_space_roles(space_id=space_id):
            if (role.get("name") or "").casefold() == name.casefold():
                return role
        return None

    def get_available_space_permissions(self) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            "/wiki/api/v2/space-permissions",
            params={"limit": 250},
        )
        return response.json().get("results", [])

    def create_space_role(
        self,
        *,
        name: str,
        description: str,
        permission_ids: list[str],
    ) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/wiki/api/v2/space-roles",
            expected=(201,),
            json={
                "name": name,
                "description": description,
                "spacePermissions": permission_ids,
            },
        )
        return response.json()

    def get_space_role_assignments(
        self,
        space_id: str,
    ) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/wiki/api/v2/spaces/{space_id}/role-assignments",
            params={"limit": 250},
        )
        return response.json().get("results", [])

    def set_space_role_assignments(
        self,
        space_id: str,
        assignments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        response = self.request(
            "POST",
            f"/wiki/api/v2/spaces/{space_id}/role-assignments",
            json=assignments,
        )
        return response.json().get("results", [])

    # ---------- Pages / attachments / restrictions ----------
    def find_page(self, space_id: str, title: str) -> dict[str, Any] | None:
        response = self.request(
            "GET",
            "/wiki/api/v2/pages",
            params={"space-id": space_id, "title": title, "limit": 25},
        )
        for page in response.json().get("results", []):
            if (page.get("title") or "") == title:
                return page
        return None

    def get_page(self, page_id: str, body_format: str = "storage") -> dict[str, Any]:
        response = self.request(
            "GET",
            f"/wiki/api/v2/pages/{page_id}",
            params={"body-format": body_format, "include-version": "true"},
        )
        return response.json()

    def create_page(self, space_id: str, title: str, storage_value: str) -> dict[str, Any]:
        response = self.request(
            "POST",
            "/wiki/api/v2/pages",
            json={
                "spaceId": space_id,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": storage_value},
            },
        )
        return response.json()

    def update_page(
        self,
        page_id: str,
        title: str,
        storage_value: str,
        next_version: int,
    ) -> dict[str, Any]:
        response = self.request(
            "PUT",
            f"/wiki/api/v2/pages/{page_id}",
            json={
                "id": page_id,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": storage_value},
                "version": {
                    "number": next_version,
                    "message": "Provisioned by Oxalis take-home utility",
                },
            },
        )
        return response.json()

    def upload_or_update_attachment(self, page_id: str, file_path: Path) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            response = self.request(
                "PUT",
                f"/wiki/rest/api/content/{page_id}/child/attachment",
                headers={"X-Atlassian-Token": "nocheck", "Accept": "application/json"},
                files={"file": (file_path.name, handle)},
                data={"minorEdit": "true", "comment": "Take-home exercise embedded image"},
            )
        return response.json()

    def get_page_attachments(self, page_id: str) -> list[dict[str, Any]]:
        response = self.request(
            "GET",
            f"/wiki/api/v2/pages/{page_id}/attachments",
            params={"limit": 100},
        )
        return response.json().get("results", [])

    def clear_content_restrictions(self, page_id: str) -> None:
        # 404 is harmless if the content currently has no restrictions.
        self.request(
            "DELETE",
            f"/wiki/rest/api/content/{page_id}/restriction",
            expected=(200,),
            allowed=(404,),
        )

    def add_user_read_restriction(self, page_id: str, account_id: str) -> None:
        self.request(
            "PUT",
            f"/wiki/rest/api/content/{page_id}/restriction/byOperation/read/user",
            params={"accountId": account_id},
        )

    def is_user_in_read_restriction(self, page_id: str, account_id: str) -> bool:
        response = self.request(
            "GET",
            f"/wiki/rest/api/content/{page_id}/restriction/byOperation/read/user",
            params={"accountId": account_id},
            allowed=(404,),
        )
        return response.status_code == 200

    def check_content_permission(self, page_id: str, account_id: str, operation: str = "read") -> bool:
        response = self.request(
            "POST",
            f"/wiki/rest/api/content/{page_id}/permission/check",
            json={
                "subject": {"type": "user", "identifier": account_id},
                "operation": operation,
            },
        )
        return bool(response.json().get("hasPermission"))
