"""
Integration test script to verify QA fixes.
This script tests the enhanced error handling and logging for the 4 problematic tools.
"""

import asyncio
import logging
import os

from assembly_client.api import AssemblyAPIClient

from assemblymcp.services import BillService, DiscoveryService, MeetingService

# Enable debug logging to see our enhanced log messages
logging.basicConfig(level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s")


async def test_bill_details_error_handling():
    """Test get_bill_details with enhanced error messages."""
    print("\n" + "=" * 60)
    print("TEST 1: get_bill_details error handling")
    print("=" * 60)

    api_key = os.getenv("ASSEMBLY_API_KEY")
    if not api_key:
        print("⚠️  ASSEMBLY_API_KEY not set, skipping integration tests")
        return

    client = AssemblyAPIClient(api_key=api_key)
    bill_service = BillService(client)

    # Test with a known bill ID
    print("\n📋 Testing with a real bill ID...")
    try:
        detail = await bill_service.get_bill_details("2100001", age="21")
        if detail:
            print(f"✅ Got bill details: {detail.bill_name}")
            print(f"   Summary length: {len(detail.summary) if detail.summary else 0}")
            print(f"   Reason length: {len(detail.reason) if detail.reason else 0}")

            if detail.summary and detail.summary.startswith("["):
                print(f"⚠️  Summary contains error message: {detail.summary[:100]}")
        else:
            print("❌ No bill details returned")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_get_api_spec_error_handling():
    """Test get_api_spec with enhanced error messages."""
    print("\n" + "=" * 60)
    print("TEST 2: get_api_spec error handling")
    print("=" * 60)

    api_key = os.getenv("ASSEMBLY_API_KEY")
    if not api_key:
        return

    client = AssemblyAPIClient(api_key=api_key)

    # Test with an invalid service ID to trigger error
    print("\n📋 Testing with invalid service ID to see error messages...")
    try:
        spec = await client.spec_parser.parse_spec("INVALID_ID_12345")
        print(f"❌ Unexpected success: {spec}")
    except Exception as e:
        error_str = str(e)
        print("✅ Got expected error with enhanced message:")
        print(f"   Error length: {len(error_str)} chars")
        if "HTML" in error_str or "troubleshooting" in error_str.lower():
            print("   ✅ Error contains diagnostic info")
        else:
            print("   ⚠️  Error may need more context")
        print(f"   Preview: {error_str[:200]}...")


async def test_call_raw_error_handling():
    """Test call_api_raw with enhanced ERROR-300 messages."""
    print("\n" + "=" * 60)
    print("TEST 3: call_api_raw error handling")
    print("=" * 60)

    api_key = os.getenv("ASSEMBLY_API_KEY")
    if not api_key:
        return

    client = AssemblyAPIClient(api_key=api_key)
    discovery = DiscoveryService(client)

    # Test with missing required parameters
    print("\n📋 Testing with incomplete parameters (should trigger ERROR-300)...")
    try:
        result = await discovery.call_raw(
            "O4K6HM0012064I15889",  # Bill search API
            {},  # No parameters - should cause ERROR-300
        )
        print(f"❌ Unexpected success: {result}")
    except Exception as e:
        error_str = str(e)
        print("✅ Got expected error:")
        if "📋 도움말" in error_str or "필수 파라미터" in error_str:
            print("   ✅ Error contains enhanced guidance")
        print(f"   Preview: {error_str[:300]}...")


async def test_search_meetings_logging():
    """Test search_meetings with enhanced logging."""
    print("\n" + "=" * 60)
    print("TEST 4: search_meetings logging")
    print("=" * 60)

    api_key = os.getenv("ASSEMBLY_API_KEY")
    if not api_key:
        return

    client = AssemblyAPIClient(api_key=api_key)
    meeting_service = MeetingService(client)

    # Test with filters that may return no results
    print("\n📋 Testing with restrictive filters (may return empty)...")
    try:
        results = await meeting_service.search_meetings(
            committee_name="법제사법위원회", date_start="2024-01-01", date_end="2024-01-31", limit=5
        )
        print(f"ℹ️  Got {len(results)} results")
        if len(results) == 0:
            print("   ✅ Check logs above for informative empty result message")
    except Exception as e:
        print(f"❌ Error: {e}")


async def main():
    """Run all QA verification tests."""
    print("\n🎯 QA Fixes Integration Test Suite")
    print("=" * 60)
    print("This tests enhanced error handling and logging")
    print("=" * 60)

    await test_bill_details_error_handling()
    await test_get_api_spec_error_handling()
    await test_call_raw_error_handling()
    await test_search_meetings_logging()

    print("\n" + "=" * 60)
    print("✅ All QA verification tests completed!")
    print("=" * 60)
    print("\nNote: Check the log output above for:")
    print("  - Debug logs showing API response inspection")
    print("  - Enhanced error messages with troubleshooting tips")
    print("  - Informative warnings when data is missing")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
