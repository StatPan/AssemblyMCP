#!/usr/bin/env python3
"""Test the SSE endpoint for MCP protocol compliance."""

import sys

import httpx


def test_sse_endpoint(url: str):
    """Test if the SSE endpoint follows MCP protocol."""
    print(f"Testing SSE endpoint: {url}")
    print("=" * 60)

    # Test 1: Check if endpoint is accessible
    print("\n[1] Checking endpoint accessibility...")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers={"Accept": "text/event-stream"})
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            print(f"Content-Type: {response.headers.get('content-type')}")

            if response.status_code != 200:
                print(f"❌ Failed: Expected 200, got {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

    # Test 2: Check SSE stream format
    print("\n[2] Checking SSE stream format...")
    try:
        with httpx.stream("GET", url, timeout=10.0) as response:
            lines_received = []
            for i, line in enumerate(response.iter_lines()):
                lines_received.append(line)
                print(f"Line {i}: {line}")
                if i >= 20:  # Read first 20 lines
                    break

            if not lines_received:
                print("❌ No SSE data received")
                return False

    except Exception as e:
        print(f"❌ Stream read failed: {e}")
        return False

    # Test 3: Check for MCP initialization endpoint
    print("\n[3] Checking MCP message endpoint...")
    try:
        # MCP over SSE typically uses POST to /messages or similar
        message_url = url.replace("/sse", "/messages")
        print(f"Trying message endpoint: {message_url}")

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

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                message_url,
                json=init_request,
                headers={"Content-Type": "application/json"},
            )
            print(f"Message endpoint status: {response.status_code}")
            print(f"Response: {response.text[:500]}")

    except Exception as e:
        print(f"⚠️  Message endpoint test failed: {e}")

    print("\n" + "=" * 60)
    print("Test completed. Review output above for issues.")
    return True


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://assembly.statpan.com/mcp/sse"
    test_sse_endpoint(url)
