from datetime import date, datetime
from typing import Any

from assemblymcp.client import AssemblyAPIClient
from assemblymcp.models import Bill


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


class BillService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        self.BILL_SEARCH_ID = "O4K6HM0012064I15889"

    def _parse_date(self, date_str: str | Any) -> date | None:
        if not isinstance(date_str, str) or not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            return None

    async def get_bill_info(
        self,
        age: str,  # REQUIRED by spec: 'AGE'
        bill_id: str | None = None,
        bill_name: str | None = None,
        propose_dt: str | None = None,
        proc_status: str | None = None,
        limit: int = 10,
    ) -> list[Bill]:
        """
        Search for legislative bills and return detailed information.
        This function integrates multiple underlying Bill APIs.
        """
        params = {
            "AGE": age,  # REQUIRED
            "BILL_ID": bill_id,
            "BILL_NAME": bill_name,
            "PROPOSE_DT": propose_dt,
            "PROC_RESULT_CD": proc_status,
            "pSize": limit,
        }
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}

        # Call the primary Bill Search API
        raw_data = await self.client.get_data(service_id=self.BILL_SEARCH_ID, params=params)

        # Structure: { service_id: [ { 'head': [...], 'row': [...] } ] }
        rows = []
        if isinstance(raw_data, dict) and self.BILL_SEARCH_ID in raw_data:
            for item in raw_data.get(self.BILL_SEARCH_ID, []):
                if "row" in item and isinstance(item["row"], list):
                    rows.extend(item["row"])

        # Transform raw data to Pydantic models
        bills = []
        for row in rows:
            try:
                bill = Bill(
                    bill_id=row.get("BILL_ID") or row.get("BILL_NO", ""),
                    bill_name=row.get("BILL_NAME", ""),
                    proposer=row.get("PROPOSER", ""),
                    proposer_kind_name=row.get("PROPOSER_KIND", "")
                    or row.get("PROPOSER_GBN_NM", ""),
                    proc_status=row.get("PROC_STATUS", "") or row.get("PROC_RESULT_NM", ""),
                    committee=row.get("CURR_COMMITTEE", "") or row.get("CMIT_NM", ""),
                    propose_dt=self._parse_date(row.get("PROPOSE_DT")),
                    committee_dt=self._parse_date(row.get("COMMITTEE_DT")),
                    proc_dt=self._parse_date(row.get("PROC_DT")),
                    link_url=row.get("LINK_URL", ""),
                )
                bills.append(bill)
            except Exception as e:
                print(f"Error converting row to Bill model: {e}")
                pass

        return bills
