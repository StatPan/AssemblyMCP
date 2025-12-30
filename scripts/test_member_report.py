import asyncio
import json
from assemblymcp.services import BillService, MeetingService, MemberService
from assemblymcp.smart import SmartService
from assembly_client.api import AssemblyAPIClient
from assemblymcp.config import settings

async def test_member_report():
    client = AssemblyAPIClient(api_key=settings.assembly_api_key)
    bill_service = BillService(client)
    meeting_service = MeetingService(client)
    member_service = MemberService(client)
    smart_service = SmartService(bill_service, meeting_service, member_service)
    
    member_name = "추경호"
    print(f"--- Generating representative report for: {member_name} ---")
    try:
        report = await smart_service.get_representative_report(member_name)
        # 통계 요약과 전문 분야(경력 분석)가 잘 나오는지 확인
        print(f"Expertise: {report.summary_stats.get('expertise_areas')}")
        print(f"Bills Count: {report.summary_stats.get('total_bills_proposed_22nd')}")
        print(f"Recent Votes Tracked: {len(report.recent_votes)}")
        
        # 전체 데이터 구조 확인 (일부)
        output = report.model_dump(exclude_none=True)
        print("\n--- Report Sample (Summary Stats) ---")
        print(json.dumps(output['summary_stats'], indent=2, ensure_ascii=False))
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_member_report())
