from datetime import date, datetime
from typing import Any

from assemblymcp.client import AssemblyAPIClient
from assemblymcp.models import Bill, BillDetail


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
        self.BILL_DETAIL_ID = "OS46YD0012559515463"

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

        return bills[:limit]

    async def search_bills(self, keyword: str) -> list[Bill]:
        """
        Smart search for bills.
        1. Tries to search by keyword in the current session (22nd).
        2. If no results, falls back to the previous session (21st).
        """
        # Try current session first
        bills = await self.get_bill_info(age="22", bill_name=keyword)
        if bills:
            return bills

        # Fallback to previous session
        bills = await self.get_bill_info(age="21", bill_name=keyword)
        return bills

    async def get_recent_bills(self, limit: int = 10) -> list[Bill]:
        """
        Get the most recent bills from the current session.
        """
        # Fetch a slightly larger batch to ensure good sorting if API doesn't sort perfectly
        bills = await self.get_bill_info(age="22", limit=max(limit, 20))

        # Sort by proposal date descending
        bills.sort(key=lambda x: x.propose_dt if x.propose_dt else date.min, reverse=True)

        return bills[:limit]

    async def get_bill_details(self, bill_id: str) -> BillDetail | None:
        """
        Get detailed information for a specific bill, including summary and proposal reason.
        """
        # 1. Get basic info first
        # We don't know the age, so we might need to search or guess.
        # For now, let's try the current session, then previous.
        # Actually, get_bill_info allows passing just bill_id if the API supports it,
        # but the Bill Search API usually requires AGE.
        # However, we can try to find it.

        # Strategy: Try to find the bill in recent sessions
        target_bill = None
        for age in ["22", "21"]:
            bills = await self.get_bill_info(age=age, bill_id=bill_id)
            if bills:
                target_bill = bills[0]
                break

        if not target_bill:
            return None

        # 2. Get detail info (Reason & Content)
        # Service ID: OS46YD0012559515463
        # This API usually takes BILL_ID or BILL_NO
        detail_service_id = self.BILL_DETAIL_ID

        summary = None
        reason = None

        try:
            raw_data = await self.client.get_data(
                service_id=detail_service_id,
                params={"BILL_NO": bill_id},  # API typically uses BILL_NO or BILL_ID
            )

            if isinstance(raw_data, dict) and detail_service_id in raw_data:
                items = raw_data[detail_service_id]
                if items:  # Just check if items exist
                    # The structure is usually [ {head: ...}, {row: ...} ] or just {row: ...} inside
                    # Let's iterate to find 'row'
                    for item in items:
                        if "row" in item:
                            rows = item["row"]
                            if rows:
                                row = rows[0]
                                # Field names might vary, need to be robust
                                # Common names: RSON_CONT (Reason), MAIN_CNTS (Main Content)
                                # Or: PROPOSE_RSON, MAJOR_CONTENT
                                # Based on "법률안 제안이유 및 주요내용", let's guess keys.
                                # Since we can't see the keys, we'll try common ones.

                                # Try to find keys that look like content
                                summary = (
                                    row.get("MAIN_CNTS") or row.get("SUMMARY") or row.get("CNTS")
                                )
                                reason = (
                                    row.get("RSON_CONT")
                                    or row.get("PROPOSE_RSON")
                                    or row.get("RSON")
                                )

        except Exception as e:
            print(f"Error fetching bill details: {e}")
            # Fallback to basic info only
            pass

        return BillDetail(**target_bill.model_dump(), summary=summary, reason=reason)


class MemberService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        self.MEMBER_INFO_ID = "OOWY4R001216HX11439"  # 국회의원 정보 통합 API

    async def get_member_info(self, name: str) -> list[dict[str, Any]]:
        """
        Search for member information by name.
        """
        params = {"HG_NM": name}
        raw_data = await self.client.get_data(service_id=self.MEMBER_INFO_ID, params=params)

        members = []
        if isinstance(raw_data, dict) and self.MEMBER_INFO_ID in raw_data:
            for item in raw_data.get(self.MEMBER_INFO_ID, []):
                if "row" in item and isinstance(item["row"], list):
                    members.extend(item["row"])
        return members


class MeetingService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        # Using "국정감사 회의록" as an example, but there are many meeting APIs.
        # A unified search might be complex, so let's start with a specific one or a few.
        # Let's use "의안 위원회심사 회의정보 조회" (OOWY4R001216HX11492) as it links to bills.
        self.MEETING_INFO_ID = "OOWY4R001216HX11492"

    async def get_meeting_records(self, bill_id: str) -> list[dict[str, Any]]:
        """
        Get meeting records related to a bill.
        """
        params = {"BILL_ID": bill_id}
        raw_data = await self.client.get_data(service_id=self.MEETING_INFO_ID, params=params)

        records = []
        if isinstance(raw_data, dict) and self.MEETING_INFO_ID in raw_data:
            for item in raw_data.get(self.MEETING_INFO_ID, []):
                if "row" in item and isinstance(item["row"], list):
                    records.extend(item["row"])
        return records
