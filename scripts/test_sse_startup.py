import os
import signal
import subprocess
import sys
import time

import requests


def main():
    print("Starting AssemblyMCP in SSE mode...")
    env = os.environ.copy()
    env["MCP_TRANSPORT"] = "sse"

    # Start the server
    process = subprocess.Popen(
        ["uv", "run", "assemblymcp"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        preexec_fn=os.setsid,  # Create new process group for clean kill
    )

    try:
        # Wait for server to start
        print("Waiting for server to start...")
        time.sleep(5)

        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            print(f"Server exited early with code {process.returncode}")
            print(f"STDOUT: {stdout.decode()}")
            print(f"STDERR: {stderr.decode()}")
            sys.exit(1)

        # Try to connect to the SSE endpoint
        # FastMCP default SSE endpoint is usually /sse
        # But we need to know the port. FastMCP usually prints it.
        # Let's read stdout to find the port.

        # Since we can't easily read stdout in real-time without blocking or threads
        # in this simple script, we'll assume default port 8000 or try a few common ones.
        # Actually, FastMCP uses uvicorn default which is 8000.

        url = "http://localhost:8000/sse"
        print(f"Connecting to {url}...")

        try:
            response = requests.get(url, stream=True, timeout=5)
            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                print("✅ SSE Endpoint is accessible!")
                # Read a bit of stream to be sure
                for line in response.iter_lines():
                    if line:
                        print(f"Received SSE data: {line.decode()}")
                        break
            else:
                print(f"❌ Failed to access SSE endpoint. Status: {response.status_code}")
                sys.exit(1)

        except requests.exceptions.ConnectionError:
            print("❌ Could not connect to server. Is it running on port 8000?")
            sys.exit(1)

    finally:
        print("Stopping server...")
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait()


if __name__ == "__main__":
    main()
