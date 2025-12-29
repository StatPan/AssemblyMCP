import logging
import re
from datetime import datetime
from typing import Any

from assembly_client.api import AssemblyAPIClient
from assembly_client.errors import AssemblyAPIError, SpecParseError

from assemblymcp.config import settings
from assemblymcp.models import Bill, BillDetail, Committee

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

        # Iterate through all service metadata
        for service_id, metadata in self.client.service_metadata.items():
            name = metadata.get("name", "")
            description = metadata.get("description", "")
            category = metadata.get("category", "")

            # Filter by keyword if provided
            if keyword:
                keyword_lower = keyword.lower()
                if not (
                    keyword_lower in name.lower()
                    or keyword_lower in description.lower()
                    or keyword_lower in service_id.lower()
                ):
                    continue

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

    async def call_raw(self, service_id_or_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """
        Call a specific API service with raw parameters.
        """
        try:
            return await self.client.get_data(service_id_or_name=service_id_or_name, params=params)
        except AssemblyAPIError as e:
            error_msg = str(e)

            # Enhance error message for missing required parameters
            if "ERROR-300" in error_msg or "필수 값 누락" in error_msg or "필수" in error_msg:
                params_list = list(params.keys()) if params else []
                enhanced_msg = (
                    f"API 호출 실패 - 필수 파라미터 누락: {error_msg}\n\n"
                    f"도움말:\n"
                    f"1. get_api_spec('{service_id_or_name}')를 호출하여 필수 파라미터 확인\n"
                    f"   (주의: 스펙 다운로드가 실패할 경우 공공데이터포털 확인 필요)\n"
                    f"2. 공공데이터포털(data.go.kr)에서 "
                    f"'{service_id_or_name}' API 명세서 직접 확인\n"
                    f"3. list_api_services()로 API 설명 확인\n\n"
                    f"현재 전달한 파라미터 ({len(params_list)}개): {params_list}\n"
                    f"일반적인 필수 파라미터: KEY (API 키), pIndex (페이지), pSize (결과 수)"
                )
                raise AssemblyAPIError(enhanced_msg) from e

            # Re-raise other API errors as-is
            raise

    async def get_preview_data(self, service_id: str) -> dict[str, Any] | None:
        """
        Fetch a single row of data for preview purposes.
        Used to provide parameter hints in get_api_spec.
        """
        try:
            # Try to get just 1 row
            params = {"pIndex": 1, "pSize": 1}
            # Use configured default age if needed, though most APIs might ignore it
            # or it might be required. Safest to include if it's a common required param.
            # But for raw calls we generally want to be minimal.
            # Let's try minimal first.

            raw_data = await self.call_raw(service_id, params=params)
            rows = _collect_rows(raw_data)
            return rows[0] if rows else None
        except Exception as e:
            logger.warning(f"Preview fetch failed for {service_id}: {e}")
            return None


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

        candidate = str(int(date_value)) if isinstance(date_value, (int, float)) else str(date_value).strip()

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
        primary_proposer, proposer_count = self._extract_proposer_info(proposer_raw or "")

        # Extract both BILL_ID and BILL_NO separately
        bill_id = self._bill_field(row, ["BILL_ID"])
        bill_no = self._bill_field(row, ["BILL_NO"])

        # If BILL_ID is missing but BILL_NO exists, use BILL_NO as fallback for bill_id
        if not bill_id and bill_no:
            bill_id = bill_no

        return Bill(
            BILL_ID=bill_id,
            BILL_NO=bill_no or None,
            BILL_NAME=self._bill_field(row, ["BILL_NAME", "BILL_NM", "BILL_TITLE"]),
            PROPOSER=proposer_raw,
            PROPOSER_KIND_NM=self._bill_field(row, ["PROPOSER_KIND", "PROPOSER_KIND_NAME", "PROPOSER_GBN_NM"]),
            PROC_STATUS=self._normalize_proc_status(row),
            CURR_COMMITTEE=self._bill_field(row, ["CURR_COMMITTEE", "CURR_COMMITTEE_NM", "CMIT_NM", "COMMITTEE"]),
            PROPOSE_DT=self._parse_date(self._bill_field(row, ["PROPOSE_DT", "PROPOSE_DATE"])),
            COMMITTEE_DT=self._parse_date(self._bill_field(row, ["COMMITTEE_DT", "CMIT_DT"])),
            PROC_DT=self._parse_date(self._bill_field(row, ["PROC_DT"])),
            LINK_URL=self._bill_field(row, ["LINK_URL", "DETAIL_LINK"]),
            PRIMARY_PROPOSER=primary_proposer,
            PROPOSER_COUNT=proposer_count,
        )

    async def get_bill_info(
        self,
        age: str,  # REQUIRED by spec: 'AGE'
        bill_id: str | None = None,
        bill_name: str | None = None,
        proposer: str | None = None,
        propose_dt: str | None = None,
        proc_status: str | None = None,
        page: int = 1,
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
            "PROPOSER": proposer,
            "PROPOSE_DT": propose_dt,
            "PROC_RESULT_CD": proc_status,
            "pIndex": page,
            "pSize": limit,
        }
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}

        # Call the primary Bill Search API
        raw_data = await self.client.get_data(service_id_or_name=self.BILL_SEARCH_ID, params=params)
        rows = _collect_rows(raw_data)

        # Transform raw data to Pydantic models
        bills = []
        for row in rows:
            try:
                bills.append(self._build_bill(row))
            except Exception as e:
                logger.warning(f"Error converting row to Bill model: {e}")

        return bills[:limit]

    async def search_bills(self, keyword: str, page: int = 1, limit: int = 10) -> list[Bill]:
        """
        Smart search for bills.
        1. Tries to search by keyword in the current session (22nd).
        2. If no results, falls back to the previous session (21st).
        """
        # Try current session first
        bills = await self.get_bill_info(age="22", bill_name=keyword, page=page, limit=limit)
        if bills:
            return bills

        # Fallback to previous session
        bills = await self.get_bill_info(age="21", bill_name=keyword, page=page, limit=limit)
        return bills

    async def get_recent_bills(self, page: int = 1, limit: int = 10) -> list[Bill]:
        """
        Get the most recent bills from the current session.
        """
        # Fetch a slightly larger batch to ensure good sorting if API doesn't sort perfectly
        bills = await self.get_bill_info(age="22", page=page, limit=max(limit, 20))

        # Sort by proposal date descending (ISO format strings sort correctly)
        bills.sort(key=lambda x: x.PROPOSE_DT if x.PROPOSE_DT else "", reverse=True)

        return bills[:limit]

    async def get_bill_details(self, bill_id: str, age: str | None = None) -> BillDetail | None:
        """
        Get detailed information for a specific bill, including summary and proposal reason.
        Args:
            bill_id: Can be either BILL_ID (alphanumeric) or BILL_NO (numeric)
            age: Optional legislative session age (e.g., "22"). If provided, skips probing.
        """
        # 1. Get basic info first
        target_bill = None

        if age:
            # If age is known, search directly
            bills = await self.get_bill_info(age=age, bill_id=bill_id)
            if bills:
                target_bill = bills[0]
        else:
            # Strategy: Try to find the bill in recent sessions
            # If bill_id looks like a numeric ID (e.g. 2214308), we can't search by BILL_ID in
            # get_bill_info because get_bill_info expects the alphanumeric ID (PRC_...).
            # However, we can try to find it by BILL_NO if we had a way to search by BILL_NO.
            # The current get_bill_info implementation maps `bill_id` arg to `BILL_ID` param.

            # Heuristic: If ID is numeric and length is around 7, it's likely a BILL_NO.
            is_numeric_id = bill_id.isdigit() and len(bill_id) < 10

            if not is_numeric_id:
                for probe_age in ["22", "21"]:
                    bills = await self.get_bill_info(age=probe_age, bill_id=bill_id)
                    if bills:
                        target_bill = bills[0]
                        break

        # If we didn't find a bill object but have a numeric ID, we might still be able to fetch
        # details directly using the numeric ID as BILL_NO.
        if not target_bill and (bill_id.isdigit() and len(bill_id) < 10):
            logger.info(
                f"Bill object not found via search, but ID {bill_id} looks like a BILL_NO. "
                "Attempting direct detail fetch."
            )
            # Create a minimal Bill object to hold the ID
            target_bill = Bill(
                BILL_ID=bill_id,  # Use the numeric ID as ID for now
                BILL_NO=bill_id,
                BILL_NAME="Unknown (Direct Fetch)",
                PROPOSER="Unknown",
                PROPOSER_KIND_NM="Unknown",
                PROC_STATUS="Unknown",
                CURR_COMMITTEE="Unknown",
                LINK_URL="",
            )

        if not target_bill:
            logger.warning(f"Bill not found in search: {bill_id}")
            return None

        # 2. Get detail info (Reason & Content)
        # Service ID: OS46YD0012559515463
        # This API requires BILL_NO (numeric bill number), not BILL_ID
        detail_service_id = self.BILL_DETAIL_ID

        summary = None
        reason = None

        # Determine which identifier to use
        # Priority: use bill_no if available, otherwise try bill_id as fallback
        bill_identifier = target_bill.BILL_NO if target_bill.BILL_NO else target_bill.BILL_ID

        try:
            # Call detail API with the numeric BILL_NO
            logger.debug(
                f"Fetching bill details: service_id={detail_service_id}, BILL_NO={bill_identifier}, bill_id={bill_id}"
            )

            raw_data = await self.client.get_data(
                service_id_or_name=detail_service_id,
                params={"BILL_NO": bill_identifier},
            )

            # Log raw response structure for debugging
            if isinstance(raw_data, dict):
                logger.debug(f"Detail API response keys: {list(raw_data.keys())[:10]}")
            else:
                logger.debug(f"Detail API response type: {type(raw_data)}")

            rows = _collect_rows(raw_data)

            if rows:
                row = rows[0]
                logger.debug(f"Detail row contains {len(row)} keys. Sample keys: {list(row.keys())[:10]}")

                # Try to extract summary
                summary = (
                    row.get("MAIN_CNTS")
                    or row.get("SUMMARY")
                    or row.get("CNTS")
                    or row.get("MAJOR_CONTENT")
                    or row.get("MAIN_CONT")
                )

                # Try to extract reason
                reason = (
                    row.get("RSON_CONT")
                    or row.get("PROPOSE_RSON")
                    or row.get("RSON")
                    or row.get("PROPOSE_REASON")
                    or row.get("RST_PROPOSE_REASON")
                )

                # If both fields are empty, provide diagnostic info
                if not summary and not reason:
                    available_keys = list(row.keys())[:15]
                    logger.warning(
                        f"Bill detail API returned data for {bill_identifier} but no "
                        f"extractable summary/reason fields. Available keys: {available_keys}"
                    )
                    summary = (
                        "[데이터 파싱 실패] API 응답 형식이 변경되었을 수 있습니다.\n"
                        f"가용 필드 ({len(row)}개): {', '.join(available_keys)}\n\n"
                        "공공데이터포털(data.go.kr)에서 최신 API 명세를 확인하거나, "
                        "AssemblyMCP 이슈 트래커에 보고해주세요."
                    )
                elif not summary:
                    logger.info(f"No summary found for bill {bill_identifier}, but reason exists")
                elif not reason:
                    logger.info(f"No reason found for bill {bill_identifier}, but summary exists")

            else:
                logger.warning(
                    f"Bill detail API returned no data rows for BILL_NO={bill_identifier}. "
                    "The API may have returned an empty response."
                )
                summary = (
                    "[상세 정보 없음] API에서 데이터를 반환하지 않았습니다.\n"
                    "가능한 원인:\n"
                    "- 의안 번호가 상세 API에 아직 등록되지 않음\n"
                    "- API 일시적 오류\n"
                    "- 의안이 너무 오래되어 상세 정보가 제공되지 않음"
                )

        except SpecParseError as e:
            logger.warning(f"Spec not available for bill detail service {detail_service_id}: {e}")
            summary = (
                f"[API 스펙 로드 실패] {detail_service_id} 서비스의 명세를 불러올 수 없습니다.\n"
                f"오류: {str(e)}\n\n"
                "공공데이터포털에서 API 명세가 변경되었을 수 있습니다."
            )
        except AssemblyAPIError as e:
            logger.warning(f"API error fetching bill details ({detail_service_id}): {e}")
            summary = (
                f"[API 호출 오류] 의안 상세 정보를 가져올 수 없습니다.\n"
                f"오류 메시지: {str(e)}\n\n"
                "잠시 후 다시 시도하거나, 공공데이터 포털 상태를 확인해주세요."
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching bill details for {bill_id}: {e}")
            summary = (
                f"[예상치 못한 오류] 의안 상세 정보 조회 중 오류가 발생했습니다.\n"
                f"오류: {type(e).__name__}: {str(e)}\n\n"
                "이 문제가 지속되면 AssemblyMCP 이슈 트래커에 보고해주세요."
            )

        return BillDetail(**target_bill.model_dump(), MAJOR_CONTENT=summary, PROPOSE_REASON=reason)


class MemberService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        # NWVRRE001000000001: 국회의원 인적사항 (Member Personal Info)
        # This seems to be the correct one for searching by name.
        # Updated to new service ID "OWSSC6001134T516707" as per issue report (backdoor solution)
        self.MEMBER_INFO_ID = "OWSSC6001134T516707"

    async def get_member_info(self, name: str) -> list[dict[str, Any]]:
        """
        Search for member information by name.
        """
        params = {"NAAS_NM": name}
        raw_data = await self.client.get_data(service_id_or_name=self.MEMBER_INFO_ID, params=params)
        rows = _collect_rows(raw_data)

        if not name:
            return rows

        normalized = re.sub(r"\s+", "", name)
        filtered = [row for row in rows if normalized in re.sub(r"\s+", "", str(row.get("HG_NM", "")))]
        return filtered or rows


class MeetingService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client

        # OR137O001023MZ19321: 위원회 회의록 (Committee Meeting Records) - Requires specific date

        self.MEETING_INFO_ID = "OR137O001023MZ19321"

        # O27DU0000960M511942: 위원회별 전체회의 일정 (Committee Schedule) - Good for range search

        self.COMMITTEE_SCHEDULE_ID = "O27DU0000960M511942"

    def _convert_unit_cd(self, age: int | str) -> str:
        """


        Convert assembly age to UNIT_CD format for schedule API.


        Example: 22 -> 100022, 21 -> 100021


        """

        try:
            val = int(age)

            if val < 1000:
                return str(100000 + val)

            return str(val)

        except ValueError:
            return str(age)

    async def get_meeting_records(self, bill_id: str) -> list[dict[str, Any]]:
        """


        Get meeting records related to a bill.


        This uses a different API (OOWY4R001216HX11492) specifically for bill-related meetings.


        """

        # OOWY4R001216HX11492: 의안 위원회심사 회의정보 조회

        bill_meeting_id = "OOWY4R001216HX11492"

        params = {"BILL_ID": bill_id}

        raw_data = await self.client.get_data(service_id_or_name=bill_meeting_id, params=params)

        return _collect_rows(raw_data)

    async def search_meetings(
        self,
        committee_name: str | None = None,
        date_start: str | None = None,
        date_end: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """


        Search for committee meetings using the Schedule API.


        This allows date range searching which the Meeting Record API doesn't support well.





        Args:


            committee_name: Name of the committee (e.g., "법제사법위원회")


            date_start: Start date (YYYY-MM-DD)


            date_end: End date (YYYY-MM-DD)


            page: Page number (default 1)


            limit: Max results


        """

        # Use Schedule API for better search capabilities

        # Fetch larger batch to ensure filtering doesn't reduce results too much

        params = {"pIndex": page, "pSize": 100}

        if committee_name:
            params["COMMITTEE_NAME"] = committee_name

        # Convert default age to UNIT_CD format (e.g. 22 -> 100022)

        params["UNIT_CD"] = self._convert_unit_cd(settings.default_assembly_age)

        raw_data = await self.client.get_data(service_id_or_name=self.COMMITTEE_SCHEDULE_ID, params=params)

        rows = _collect_rows(raw_data)

        logger.debug(
            f"Meeting schedule search returned {len(rows)} raw results for filters: committee={committee_name}"
        )

        # Post-filtering by date

        filtered = []

        for row in rows:
            # Schedule API returns MEETING_DATE (YYYY-MM-DD)

            meeting_date = row.get("MEETING_DATE", "")

            # Simple string comparison works for ISO format dates

            if date_start and meeting_date < date_start:
                continue

            if date_end and meeting_date > date_end:
                continue

            # Remap fields to match expected output format (closer to Meeting Record API)

            # MEETING_DATE -> CONF_DATE (without hyphens usually, but let's keep it ISO or normalize?)

            # The original API used YYYYMMDD. Let's provide both or standardize.

            # Let's keep MEETING_DATE as is and add CONF_DATE for compatibility.

            normalized_row = row.copy()

            normalized_row["CONF_DATE"] = meeting_date.replace("-", "")  # YYYYMMDD

            normalized_row["CONF_TITLE"] = row.get("TITLE", "")

            filtered.append(normalized_row)

        # Sort by date descending (newest first)

        filtered.sort(key=lambda x: x.get("MEETING_DATE", ""), reverse=True)

        result = filtered[:limit]

        if not result:
            logger.info(
                f"No meeting records found. Filters used: "
                f"committee='{committee_name}', date_start='{date_start}', "
                f"date_end='{date_end}'. "
                f"Raw results: {len(rows)}"
            )

        return result

    async def get_plenary_schedule(
        self,
        unit_cd: str | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Get plenary meeting schedule.
        Service ID: ORDPSW001070QH19059 (본회의 일정)
        """
        service_id = "ORDPSW001070QH19059"
        params = {"pIndex": page, "pSize": limit}

        if unit_cd:
            # The API expects 1000xx format (e.g., 100022 for 22nd assembly)
            # If user provides "22" or "22대", we handle it gracefully.
            clean_unit_cd = re.sub(r"[^0-9]", "", str(unit_cd))
            if len(clean_unit_cd) > 0 and len(clean_unit_cd) <= 2:
                clean_unit_cd = f"1000{clean_unit_cd}"
            params["UNIT_CD"] = clean_unit_cd

        raw_data = await self.client.get_data(service_id_or_name=service_id, params=params)
        return _collect_rows(raw_data)


class CommitteeService:
    def __init__(self, client: AssemblyAPIClient):
        self.client = client
        # O2Q4ZT001004PV11014: 위원회 현황 정보 (Committee Status Info)
        self.COMMITTEE_INFO_ID = "O2Q4ZT001004PV11014"
        # OCAJQ4001000LI18751: 위원회 위원 명단 (Committee Member Roster)
        self.COMMITTEE_MEMBER_LIST_ID = "OCAJQ4001000LI18751"

    async def get_committee_list(self, committee_name: str | None = None) -> list[Committee]:
        """
        Get a list of committees.
        """
        params = {}
        if committee_name:
            params["COMMITTEE_NAME"] = committee_name

        raw_data = await self.client.get_data(service_id_or_name=self.COMMITTEE_INFO_ID, params=params)
        rows = _collect_rows(raw_data)

        committees = []
        for row in rows:
            try:
                committees.append(
                    Committee(
                        HR_DEPT_CD=str(row.get("HR_DEPT_CD", "")),
                        COMMITTEE_NAME=str(row.get("COMMITTEE_NAME", "")),
                        CMT_DIV_NM=str(row.get("CMT_DIV_NM", "")),
                        HG_NM=row.get("HG_NM"),
                        CURR_CNT=int(row.get("CURR_CNT")) if row.get("CURR_CNT") else None,
                        LIMIT_CNT=int(row.get("LIMIT_CNT")) if row.get("LIMIT_CNT") else None,
                    )
                )
            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error parsing committee row: {e}", exc_info=True)
            except Exception as e:
                logger.warning(f"Unexpected error parsing committee row: {e}", exc_info=True)

        return committees

    async def get_committee_members(
        self,
        committee_code: str | None = None,
        committee_name: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get roster (members) for a committee.

        The underlying API accepts either committee code (HR_DEPT_CD) or committee name.
        This helper tries both and also post-filters by name to maximize recall.
        """
        params: dict[str, Any] = {"pIndex": page, "pSize": min(limit, 100)}

        # Prefer explicit code when provided
        if committee_code:
            params["HR_DEPT_CD"] = committee_code
        if committee_name:
            params["COMMITTEE_NAME"] = committee_name

        raw_data = await self.client.get_data(service_id_or_name=self.COMMITTEE_MEMBER_LIST_ID, params=params)

        # Explicitly check for INFO-200 (No corresponding data) from the raw API response
        # Structure is usually { "service_name": [ { "head": [...] }, { "row": [...] } ] }
        # or just { "RESULT": { "CODE": "...", "MESSAGE": "..." } }
        service_key = list(raw_data.keys())[0] if raw_data else None
        if service_key and isinstance(raw_data[service_key], list) and len(raw_data[service_key]) > 0:
            head_section = raw_data[service_key][0].get("head")
            if head_section and len(head_section) > 1:
                result = head_section[1].get("RESULT")
                if result and result.get("CODE") == "INFO-200":
                    msg = result.get("MESSAGE")

                    error_details = {
                        "error_type": "DATA_NOT_FOUND",
                        "api_code": result.get("CODE"),
                        "api_message": msg,
                        "query_info": {
                            "committee_name": committee_name,
                            "committee_code": committee_code,
                        },
                        "suggestion": (
                            "이 위원회에 대한 위원 명단 데이터가 국회 OpenAPI에 없거나, "
                            "검색 조건(이름)이 정확하지 않을 수 있습니다. "
                            "get_committee_list()를 호출하여 정확한 committee_code를 "
                            "확인 후 다시 시도하거나, 다른 검색어를 사용해보세요."
                        ),
                    }

                    # If searched by name and no code, try to find suggestions
                    if committee_name and not committee_code:
                        try:
                            candidates = await self.get_committee_list(committee_name=committee_name)
                            valid_candidates = []
                            for c in candidates:
                                if c.committee_code and c.committee_code != "None":
                                    valid_candidates.append(f"{c.committee_name}(코드: {c.committee_code})")

                            if valid_candidates:
                                error_details["suggestion"] = (
                                    f"입력하신 위원회명 '{committee_name}'에 대해 "
                                    "위원 명단을 찾을 수 없습니다. "
                                    f"다음과 같은 관련 위원회가 있습니다. "
                                    f"해당 코드(committee_code)로 재시도해보세요: "
                                    f"{', '.join(valid_candidates)}"
                                )
                            else:
                                error_details["suggestion"] = (
                                    f"'{committee_name}'(으)로 검색된 위원회 중 "
                                    f"유효한 코드(HR_DEPT_CD)를 가진 위원회가 없습니다. "
                                    "이는 해당 위원회 명단이 OpenAPI에 없거나, "
                                    "이름이 정확하지 않을 수 있습니다. "
                                    "get_committee_list()를 호출하여 "
                                    "전체 위원회 목록을 확인해보세요."
                                )
                        except Exception as e:
                            logger.warning(f"Error generating suggestions for '{committee_name}': {e}")
                            # Fallback to generic suggestion if suggestion generation fails

                    return {"error": error_details}

        rows = _collect_rows(raw_data)

        # CRITICAL FIX: The API sometimes ignores HR_DEPT_CD and returns all members.
        # We must manually filter by committee_code if it was provided.
        if committee_code:
            rows = [row for row in rows if str(row.get("DEPT_CD") or row.get("HR_DEPT_CD") or "") == committee_code]

        # If a name was provided, post-filter in case the API lacks fuzzy matching
        if committee_name:
            normalized = re.sub(r"\s+", "", committee_name)
            filtered = []
            for row in rows:
                row_name = re.sub(r"\s+", "", str(row.get("COMMITTEE_NAME", "")))
                if normalized in row_name:
                    filtered.append(row)

            # CRITICAL FIX: If filtering yields results, use them.
            # If filtering yields NOTHING, it means the name didn't match.
            # Previously we fell back to 'rows', which returned the entire list (bad).
            # If 'filtered' is empty, BUT 'rows' was not empty
            # (meaning we had candidates but none matched), return empty.
            if rows and not filtered:
                return []
            if filtered:
                rows = filtered

        return rows[:limit]
