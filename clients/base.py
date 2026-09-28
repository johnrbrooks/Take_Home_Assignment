from __future__ import annotations

import json
import time
from typing import Iterable
from urllib.parse import urljoin

import requests

from common.errors import (
    ApiFailure,
    AtlassianApiError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    RateLimitError,
    ResourceNotFoundError,
)


class BaseHttpClient:
    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.session = session or requests.Session()

    def _url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.base_url, path_or_url.lstrip("/"))

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        expected: Iterable[int] = (200,),
        allowed: Iterable[int] = (),
        timeout: int = 30,
        max_retries: int = 3,
        **kwargs,
    ) -> requests.Response:
        url = self._url(path_or_url)
        expected_set = set(expected)
        allowed_set = set(allowed)
        last_response: requests.Response | None = None

        for attempt in range(max_retries + 1):
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
            except requests.RequestException as exc:
                if attempt >= max_retries:
                    raise AtlassianApiError(
                        f"Network request failed: {exc}",
                        ApiFailure(0, method.upper(), url, str(exc)),
                        "Check network connectivity, site URL, and proxy/VPN settings.",
                    ) from exc
                time.sleep(min(2 ** attempt, 8))
                continue

            last_response = response
            if response.status_code in expected_set or response.status_code in allowed_set:
                return response

            should_retry = response.status_code == 429 or 500 <= response.status_code <= 599
            if should_retry and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = float(retry_after) if retry_after else float(2 ** attempt)
                except ValueError:
                    delay = float(2 ** attempt)
                time.sleep(min(max(delay, 1.0), 10.0))
                continue

            self._raise_for_response(response, method.upper(), url)

        assert last_response is not None
        self._raise_for_response(last_response, method.upper(), url)
        raise AssertionError("unreachable")

    @staticmethod
    def _response_body(response: requests.Response) -> str:
        try:
            return json.dumps(response.json(), ensure_ascii=False)
        except ValueError:
            return response.text.strip() or "<empty response body>"

    def _raise_for_response(self, response: requests.Response, method: str, url: str) -> None:
        body = self._response_body(response)
        failure = ApiFailure(response.status_code, method, url, body)
        message = f"Atlassian API request failed: {method} {url} -> HTTP {response.status_code}"

        if response.status_code == 401:
            raise AuthenticationError(
                message,
                "Verify the API token/API key and the account used for authentication.",
            )
        if response.status_code == 403:
            raise AuthorizationError(
                f"{message}\nResponse: {body}",
                "The credential is valid but does not have the required admin/space permission.",
            )
        if response.status_code == 404:
            raise ResourceNotFoundError(f"{message}\nResponse: {body}")
        if response.status_code == 409:
            raise ConflictError(f"{message}\nResponse: {body}")
        if response.status_code == 429:
            raise RateLimitError(
                f"{message}\nResponse: {body}",
                "Wait for the Atlassian rate-limit window to reset and retry.",
            )
        raise AtlassianApiError(f"{message}\nResponse: {body}", failure)
