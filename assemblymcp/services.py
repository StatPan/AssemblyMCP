from typing import Any

from assemblymcp.client import AssemblyAPIClient


class DiscoveryService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client

    async def list_services(self, keyword: str = "") -> list[dict[str, str]]:
        """
        Search for available API services by keyword.
        """
        results = []
        for service_id, spec in self.client.specs.items():
            name = spec.get("INF_NM", "")
            description = spec.get("INF_EXP", "")
            category = spec.get("CATE_NM", "")

            if (
                not keyword
                or keyword.lower() in name.lower()
                or keyword.lower() in description.lower()
            ):
                results.append(
                    {
                        "id": service_id,
                        "name": name,
                        "category": category,
                        "description": description,
                    }
                )

        # Sort by name
        results.sort(key=lambda x: x["name"])
        return results

    async def call_raw(self, service_id: str, params: dict[str, Any]) -> dict[str, Any] | str:
        """
        Call a specific API service with raw parameters.
        """
        return await self.client.get_data(service_id=service_id, params=params)
