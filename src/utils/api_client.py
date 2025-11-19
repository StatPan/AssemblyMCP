"""Base API client for National Assembly OpenAPI."""

from typing import Any

import httpx

from .config import BASE_URL, get_api_key


class AssemblyAPIClient:
    """Client for National Assembly OpenAPI."""

    def __init__(self, api_key: str | None = None):
        """Initialize API client.

        Args:
            api_key: API key. If not provided, read from environment variable.
        """
        self.api_key = api_key or get_api_key()
        self.base_url = BASE_URL

    def request(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        response_type: str = "json",
    ) -> dict[str, Any]:
        """Make API request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            response_type: Response type (json or xml)

        Returns:
            API response as dictionary
        """
        url = f"{self.base_url}/{endpoint}"

        default_params = {
            "KEY": self.api_key,
            "Type": response_type,
            "pIndex": 1,
            "pSize": 10,
        }

        if params:
            default_params.update(params)

        response = httpx.get(url, params=default_params, timeout=30.0)
        response.raise_for_status()

        return response.json()
