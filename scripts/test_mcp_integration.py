import json
import os
import subprocess
import sys


def send_request(process, request):
    json_str = json.dumps(request)
    process.stdin.write(f"{json_str}\n".encode())
    process.stdin.flush()


def read_response(process):
    while True:
        line = process.stdout.readline()
        if not line:
            return None
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            print(f"LOG: {line.decode('utf-8').strip()}")
            continue


def main():
    # Start the MCP server
    print("Starting AssemblyMCP server...")
    env = os.environ.copy()
    # Ensure we use the same python environment
    process = subprocess.Popen(
        ["uv", "run", "assemblymcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        env=env,
    )

    try:
        # 1. Initialize
        print("\nSending initialize request...")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-script", "version": "1.0"},
            },
        }
        send_request(process, init_req)
        resp = read_response(process)
        print(f"Initialize Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

        if not resp or "error" in resp:
            print("Initialization failed!")
            return

        # 2. Initialized notification
        send_request(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        # 3. List Tools
        print("\nListing tools...")
        list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        send_request(process, list_req)
        resp = read_response(process)
        # print(f"Tools List Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # 4. Call 'get_assembly_info'
        print("\nCalling get_assembly_info...")
        call_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "get_assembly_info", "arguments": {}},
        }
        send_request(process, call_req)
        resp = read_response(process)
        print(f"Call Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

        # 5. Call 'search_bills' with pagination
        print("\nCalling search_bills with page=2...")
        search_req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "search_bills",
                "arguments": {"keyword": "예산", "page": 2, "limit": 1},
            },
        }
        send_request(process, search_req)
        resp = read_response(process)
        print(f"Search Response: {json.dumps(resp, indent=2, ensure_ascii=False)}")

    finally:
        process.terminate()
        process.wait()


if __name__ == "__main__":
    main()
