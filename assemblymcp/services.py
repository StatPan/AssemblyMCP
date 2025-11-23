import logging
import re
from datetime import datetime
from typing import Any

from assemblymcp.client import AssemblyAPIClient, AssemblyAPIError
from assemblymcp.models import Bill, BillDetail, Committee
from assemblymcp.spec_parser import SpecParseError

logger = logging.getLogger(__name__)


def _collect_rows(raw_data: Any) -> list[dict[str, Any]]:
    """Walk nested API response objects and return every dict row."""
    rows: list[dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "row" in node and isinstance(node["row"], list):
                for entry in node["row"]:
                    if isinstance(entry, dict):
                        rows.append(entry)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(raw_data)
    return rows


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
        self._proc_status_map = {
            "1000": "접수",
            "2000": "위원회 심사",
            "3000": "본회의 심의",
            "4000": "의결",
            "5000": "폐기",
        }

    def _parse_date(self, date_value: Any) -> str | None:
        if date_value is None:
            return None

        if isinstance(date_value, (int, float)):
            candidate = str(int(date_value))
        else:
            candidate = str(date_value).strip()

        if not candidate:
            return None

        for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                parsed = datetime.strptime(candidate, fmt).date()
                return parsed.isoformat()
            except ValueError:
                continue

        digits_only = re.sub(r"[^0-9]", "", candidate)
        if len(digits_only) == 8:
            try:
                parsed = datetime.strptime(digits_only, "%Y%m%d").date()
                return parsed.isoformat()
            except ValueError:
                return None

        return None

    def _bill_field(self, row: dict[str, Any], keys: list[str], default: str = "") -> str:
        for key in keys:
            value = row.get(key)
            if value is None:
                continue
            if isinstance(value, str):
                value = value.strip()
            if value != "":
                return str(value)
        return default

    def _extract_proposer_info(self, raw_text: str) -> tuple[str | None, int | None]:
        if not raw_text:
            return None, None
        text = raw_text.strip()
        if not text:
            return None, None

        match = re.search(r"^(?P<name>.+?)(?:\s*의원)?\s*(?:등|외)\s*(?P<count>\d+)(?:인|명)", text)
        if match:
            primary = match.group("name").strip()
            try:
                count = int(match.group("count")) + 1
            except ValueError:
                count = None
            return primary or None, count

        return text, None

    def _normalize_proc_status(self, row: dict[str, Any]) -> str:
        status = self._bill_field(
            row,
            [
                "PROC_STATUS",
                "PROC_RESULT_NM",
                "CURR_STATUS",
                "PROCESS_STAGE",
                "LAST_RESULT",
                "PROC_STATE",
            ],
        )
        if status:
            return status

        code = row.get("PROC_RESULT_CD") or row.get("PROC_STATUS_CD")
        if code:
            return self._proc_status_map.get(str(code), str(code))
        return ""

    def _build_bill(self, row: dict[str, Any]) -> Bill:
        proposer_raw = self._bill_field(row, ["PROPOSER", "PROPOSER_MAIN_NM", "RST_PROPOSER"])
        proposer_text = proposer_raw or None
        primary_proposer, proposer_count = self._extract_proposer_info(proposer_raw or "")

        # Extract both BILL_ID and BILL_NO separately
        bill_id = self._bill_field(row, ["BILL_ID"])
        bill_no = self._bill_field(row, ["BILL_NO"])

        # If BILL_ID is missing but BILL_NO exists, use BILL_NO as fallback for bill_id
        if not bill_id and bill_no:
            bill_id = bill_no

        return Bill(
            bill_id=bill_id,
            bill_no=bill_no or None,
            bill_name=self._bill_field(row, ["BILL_NAME", "BILL_NM", "BILL_TITLE"]),
            proposer=proposer_raw,
            proposer_kind_name=self._bill_field(
                row, ["PROPOSER_KIND", "PROPOSER_KIND_NAME", "PROPOSER_GBN_NM"]
            ),
            proc_status=self._normalize_proc_status(row),
            committee=self._bill_field(
                row, ["CURR_COMMITTEE", "CURR_COMMITTEE_NM", "CMIT_NM", "COMMITTEE"]
            ),
            propose_dt=self._parse_date(self._bill_field(row, ["PROPOSE_DT", "PROPOSE_DATE"])),
            committee_dt=self._parse_date(self._bill_field(row, ["COMMITTEE_DT", "CMIT_DT"])),
            proc_dt=self._parse_date(self._bill_field(row, ["PROC_DT"])),
            link_url=self._bill_field(row, ["LINK_URL", "DETAIL_LINK"]),
            proposer_text=proposer_text,
            primary_proposer=primary_proposer,
            proposer_count=proposer_count,
        )

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
        rows = _collect_rows(raw_data)

        # Transform raw data to Pydantic models
        bills = []
        for row in rows:
            try:
                bills.append(self._build_bill(row))
            except Exception as e:
                logger.warning(f"Error converting row to Bill model: {e}")

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

        # Sort by proposal date descending (ISO format strings sort correctly)
        bills.sort(key=lambda x: x.propose_dt if x.propose_dt else "", reverse=True)

        return bills[:limit]

    async def get_bill_details(self, bill_id: str) -> BillDetail | None:
        """
        Get detailed information for a specific bill, including summary and proposal reason.
        Args:
            bill_id: Can be either BILL_ID (alphanumeric) or BILL_NO (numeric)
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
        # This API requires BILL_NO (numeric bill number), not BILL_ID
        detail_service_id = self.BILL_DETAIL_ID

        summary = None
        reason = None

        # Determine which identifier to use
        # Priority: use bill_no if available, otherwise try bill_id as fallback
        bill_identifier = target_bill.bill_no if target_bill.bill_no else target_bill.bill_id

        try:
            # Call detail API with the numeric BILL_NO
            raw_data = await self.client.get_data(
                service_id=detail_service_id,
                params={"BILL_NO": bill_identifier},
            )

            rows = _collect_rows(raw_data)
            if rows:
                row = rows[0]
                summary = (
                    row.get("MAIN_CNTS")
                    or row.get("SUMMARY")
                    or row.get("CNTS")
                    or row.get("MAJOR_CONTENT")
                    or row.get("MAIN_CONT")
                )
                reason = (
                    row.get("RSON_CONT")
                    or row.get("PROPOSE_RSON")
                    or row.get("RSON")
                    or row.get("PROPOSE_REASON")
                    or row.get("RST_PROPOSE_REASON")
                )
        except SpecParseError as e:
            logger.warning(
                "Spec not available for bill detail service %s: %s", detail_service_id, e
            )
        except AssemblyAPIError as e:
            logger.warning("API error fetching bill details (%s): %s", detail_service_id, e)
        except Exception as e:
            logger.exception("Unexpected error fetching bill details for %s: %s", bill_id, e)

        return BillDetail(**target_bill.model_dump(), summary=summary, reason=reason)


class MemberService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        self.MEMBER_INFO_ID = "OOWY4R001216HX11439"  # 국회의원 정보 통합 API

    async def get_member_info(self, name: str) -> list[dict[str, Any]]:
        """
        Search for member information by name.
        """
        params = {"NAAS_NM": name}
        raw_data = await self.client.get_data(service_id=self.MEMBER_INFO_ID, params=params)
        rows = _collect_rows(raw_data)

        if not name:
            return rows

        normalized = re.sub(r"\s+", "", name)
        filtered = [
            row for row in rows if normalized in re.sub(r"\s+", "", str(row.get("HG_NM", "")))
        ]
        return filtered or rows


class MeetingService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        # OR137O001023MZ19321: 위원회 회의록 (Committee Meeting Records)
        self.MEETING_INFO_ID = "OR137O001023MZ19321"

    async def get_meeting_records(self, bill_id: str) -> list[dict[str, Any]]:
        """
        Get meeting records related to a bill.
        This uses a different API (OOWY4R001216HX11492) specifically for bill-related meetings.
        """
        # OOWY4R001216HX11492: 의안 위원회심사 회의정보 조회
        bill_meeting_id = "OOWY4R001216HX11492"
        params = {"BILL_ID": bill_id}
        raw_data = await self.client.get_data(service_id=bill_meeting_id, params=params)
        return _collect_rows(raw_data)

    async def search_meetings(
        self,
        committee_name: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for committee meetings.

        Args:
            committee_name: Name of the committee (e.g., "법제사법위원회")
            date_start: Start date (YYYY-MM-DD)
            date_end: End date (YYYY-MM-DD)
            limit: Max results
        """
        params = {"pSize": limit}

        if committee_name:
            params["COMM_NAME"] = committee_name

        # The API usually takes a single date or a range if supported,
        # but the spec for OR137O001023MZ19321 typically has CONF_DATE.
        # Let's check if we can filter by date.
        # If the API only supports exact match on CONF_DATE, we might need to fetch and filter.
        # For now, let's pass it if provided, but we might need to refine this
        # based on actual API behavior.
        if date_start:
            params["CONF_DATE"] = date_start.replace("-", "")

        # Note: The API might not support range queries directly.
        # We will fetch and filter if necessary, but for now let's try basic params.

        # Also, DAE_NUM (Age) is often required. Let's default to current (22).
        params["DAE_NUM"] = "22"

        raw_data = await self.client.get_data(service_id=self.MEETING_INFO_ID, params=params)
        rows = _collect_rows(raw_data)

        # Post-filtering if needed (e.g. date range)
        filtered = []
        for row in rows:
            conf_date = row.get("CONF_DATE", "")
            if date_start and conf_date < date_start.replace("-", ""):
                continue
            if date_end and conf_date > date_end.replace("-", ""):
                continue
            filtered.append(row)

        return filtered[:limit]


class CommitteeService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        # O2Q4ZT001004PV11014: 위원회 현황 정보 (Committee Status Info)
        self.COMMITTEE_INFO_ID = "O2Q4ZT001004PV11014"

    async def get_committee_list(self, committee_name: str | None = None) -> list[Committee]:
        """
        Get a list of committees.
        """
        params = {}
        if committee_name:
            params["COMMITTEE_NAME"] = committee_name

        raw_data = await self.client.get_data(service_id=self.COMMITTEE_INFO_ID, params=params)
        rows = _collect_rows(raw_data)

        committees = []
        for row in rows:
            try:
                committees.append(
                    Committee(
                        committee_code=str(row.get("HR_DEPT_CD", "")),
                        committee_name=str(row.get("COMMITTEE_NAME", "")),
                        committee_div=str(row.get("CMT_DIV_NM", "")),
                        chairperson=row.get("HG_NM"),
                        member_count=int(row.get("CURR_CNT")) if row.get("CURR_CNT") else None,
                        limit_count=int(row.get("LIMIT_CNT")) if row.get("LIMIT_CNT") else None,
                    )
                )
            except Exception as e:
                logger.warning(f"Error parsing committee row: {e}")

        return committees
