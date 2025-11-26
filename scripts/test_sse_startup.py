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

    # Determine platform for process group handling
    is_windows = sys.platform == "win32"

    popen_kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
    }

    if is_windows:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["preexec_fn"] = os.setsid

    # Start the server
    process = subprocess.Popen(["uv", "run", "assemblymcp"], **popen_kwargs)

    try:
        # Wait for server to start using polling
        print("Waiting for server to start...")
        url = "http://localhost:8000/sse"
        server_started = False

        for _ in range(10):  # Poll for up to 10 seconds
            if process.poll() is not None:
                break  # Server exited prematurely
            try:
                # A simple HEAD request is enough to check for connection
                requests.head(url, timeout=1)
                print("Server is up!")
                server_started = True
                break
            except requests.exceptions.ConnectionError:
                time.sleep(1)

        if not server_started:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                print(f"Server exited early with code {process.returncode}")
                print(f"STDOUT: {stdout.decode()}")
                print(f"STDERR: {stderr.decode()}")
            else:
                print("❌ Server did not start within the timeout period.")
            sys.exit(1)

        # Try to connect to the SSE endpoint
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
        if is_windows:
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait()


if __name__ == "__main__":
    main()
