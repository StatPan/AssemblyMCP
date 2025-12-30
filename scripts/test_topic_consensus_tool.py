import asyncio
import json
from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService
from assembly_client.api import AssemblyAPIClient
from assemblymcp.config import settings

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
        report = await smart_service.get_topic_political_consensus(topic, limit=5)
        print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_topic_consensus())
