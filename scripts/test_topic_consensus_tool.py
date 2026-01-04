import asyncio
import json

from assembly_client.api import AssemblyAPIClient

from assemblymcp.config import settings
from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService


async def test_topic_consensus():
    # Ensure client is initialized with API key from environment (loaded via settings)
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
    bill_service = BillService(client)
    meeting_service = MeetingService(client)
    member_service = MemberService(client)
    smart_service = SmartService(bill_service, meeting_service, member_service)

    topic = "응급의료"
    print(f"--- Analyzing political consensus for topic: {topic} ---")
    try:
        report = await smart_service.analyze_voting_trends(topic)
        print(json.dumps(report, indent=2, ensure_ascii=False))
    except Exception as e:
        import traceback

        traceback.print_exc()
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_topic_consensus())
