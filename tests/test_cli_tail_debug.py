"""
Debug why CLI tail is hanging.
"""

import asyncio
import sys
from pathlib import Path

import pexpect
import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
async def test_cli_tail_basic_debug(climux_server, climux_client):
    """
    Basic debug test for CLI tail functionality.
    """
    # Start a long-running process
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                "import time; print('Starting', flush=True); time.sleep(2); print('Still running', flush=True); time.sleep(1)",
            ],
            "name": "debug_test",
        },
    )
    process_id = result["id"]

    # Give it time to start
    await asyncio.sleep(0.5)

    # Verify logs exist
    logs = await climux_client.request("logs", {"id": process_id})
    print(f"Initial logs: {logs}")

    # Start tailing with debug output
    cmd = f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}"
    print(f"Running: {cmd}")

    child = pexpect.spawn(cmd, encoding="utf-8", timeout=10)

    # Enable debug logging
    child.logfile_read = sys.stdout

    try:
        # Wait for any output
        print("\nWaiting for output...")
        index = await child.expect([pexpect.TIMEOUT, pexpect.EOF, r".+"], async_=True)

        print(f"\nResult: index={index}")
        print(f"Before: {child.before!r}")
        print(f"After: {child.after!r}")
        print(f"Buffer: {child.buffer!r}")

        if index == 2:  # Got some output
            # Try to read more
            await asyncio.sleep(1)
            try:
                more = child.read_nonblocking(1000, timeout=0.1)
                print(f"Additional output: {more!r}")
            except:
                pass

    finally:
        # Stop the process
        await climux_client.request("stop", {"id": process_id})

        if child.isalive():
            child.close(force=True)
