#!/usr/bin/env python3
"""Test the Streamable HTTP endpoint for MCP protocol compliance."""

import json
import sys
import time

import httpx


def parse_sse_response(text: str) -> dict | None:
    """Parse SSE formatted response to extract JSON data."""
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            data_str = line[6:]  # Remove "data: " prefix
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                continue
    return None


def test_streamable_http(base_url: str):
    """Test if the Streamable HTTP endpoint follows MCP protocol."""
    print(f"Testing Streamable HTTP endpoint: {base_url}")
    print("=" * 60)

    # Use persistent session for Streamable HTTP
    session_id = None

    # Test 1: Send initialize request
    print("\n[1] Sending initialize request...")
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                base_url,
                json=init_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")

            # Extract session ID for subsequent requests
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                print(f"Session ID: {session_id}")

            if response.status_code == 200:
                # Parse SSE response
                data = parse_sse_response(response.text)
                if data:
                    print(f"✅ Response: {json.dumps(data, indent=2, ensure_ascii=False)}")

                    if "result" in data:
                        print("\n✅ Initialize successful!")
                        print(f"Server: {data['result'].get('serverInfo', {})}")
                        print(f"Capabilities: {data['result'].get('capabilities', {})}")
                    elif "error" in data:
                        print(f"\n❌ Error response: {data['error']}")
                        return False
                else:
                    print(f"❌ Failed to parse SSE response: {response.text[:500]}")
                    return False
            else:
                print(f"❌ Failed: Expected 200, got {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False

    except httpx.ConnectError as e:
        print(f"❌ Connection failed: {e}")
        print("Make sure the server is running!")
        return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

    # Test 2: List tools
    print("\n[2] Sending tools/list request...")
    list_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

    try:
        with httpx.Client(timeout=30.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if session_id:
                headers["mcp-session-id"] = session_id

            response = client.post(
                base_url,
                json=list_request,
                headers=headers,
            )

            if response.status_code == 200:
                data = parse_sse_response(response.text)
                if data and "result" in data and "tools" in data["result"]:
                    tools = data["result"]["tools"]
                    print(f"✅ Found {len(tools)} tools")
                    for tool in tools[:3]:  # Show first 3
                        print(f"  - {tool.get('name')}: {tool.get('description', '')[:60]}...")
                else:
                    print(f"⚠️  Unexpected response format")
            else:
                print(f"❌ Failed: Status {response.status_code}")
                return False

    except Exception as e:
        print(f"❌ List tools failed: {e}")
        return False

    # Test 3: Call a tool (ping)
    print("\n[3] Calling ping tool...")
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "ping", "arguments": {}},
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            if session_id:
                headers["mcp-session-id"] = session_id

            response = client.post(
                base_url,
                json=call_request,
                headers=headers,
            )

            if response.status_code == 200:
                data = parse_sse_response(response.text)
                if data:
                    print(f"✅ Tool call response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            else:
                print(f"⚠️  Tool call failed: Status {response.status_code}")

    except Exception as e:
        print(f"⚠️  Tool call error: {e}")

    print("\n" + "=" * 60)
    print("✅ All tests completed successfully!")
    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/mcp"
    success = test_streamable_http(url)
    sys.exit(0 if success else 1)
