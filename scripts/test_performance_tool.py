import asyncio
import json

from assembly_client.api import AssemblyAPIClient

from assemblymcp.config import settings
from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService


async def test_performance():
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
    bill_service = BillService(client)
    meeting_service = MeetingService(client)
    member_service = MemberService(client)
    smart_service = SmartService(bill_service, meeting_service, member_service)

    committee = "법제사법위원회"
    print(f"--- Analyzing performance for {committee} ---")
    try:
        report = await smart_service.get_committee_voting_stats(committee)
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_performance())
