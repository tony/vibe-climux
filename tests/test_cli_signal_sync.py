"""
Test signal-based synchronization for CLI streaming with pexpect.
"""

import asyncio
import os
import signal
import sys
from pathlib import Path

import pexpect
import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
async def test_signal_based_synchronization(climux_server, climux_client):
    """
    Demonstrates signal-based synchronization for deterministic testing.
    """
    # Start a process that waits for a signal
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                """import signal, sys, time

def handler(sig, frame):
    print('SIGNAL RECEIVED', flush=True)
    print('Starting output...', flush=True) 
    for i in range(3):
        print(f'Output line {i}', flush=True)
        time.sleep(0.1)
    print('Done outputting', flush=True)
    sys.exit(0)

signal.signal(signal.SIGUSR1, handler)
print('READY FOR SIGNAL', flush=True)

# Keep alive
while True:
    time.sleep(0.1)
""",
            ],
            "name": "signal_process",
        },
    )
    process_id = result["id"]
    process_pid = result["pid"]

    # Wait for process to be ready
    await asyncio.sleep(1)

    # Verify the process has logged its ready message
    logs = await climux_client.request("logs", {"id": process_id})
    assert any("READY FOR SIGNAL" in log["content"] for log in logs)

    # Start tailing
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=15,
    )

    try:
        # The tail command outputs existing logs first
        # We should see the READY message
        index = await child.expect([r"READY FOR SIGNAL", pexpect.TIMEOUT], async_=True)
        if index == 0:
            print("✓ Saw READY FOR SIGNAL in tail output")

        # Now send the signal
        print(f"Sending SIGUSR1 to process {process_pid}")
        os.kill(process_pid, signal.SIGUSR1)

        # Should see the signal handler output
        index = await child.expect([r"SIGNAL RECEIVED", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see SIGNAL RECEIVED"
        print("✓ Process received signal")

        # Verify we see the output lines
        for i in range(3):
            index = await child.expect(
                [rf"Output line {i}", pexpect.TIMEOUT], async_=True
            )
            assert index == 0, f"Should see output line {i}"
            print(f"✓ Saw output line {i}")

        # Should see completion
        index = await child.expect([r"Done outputting", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see completion message"
        print("✓ Process completed output")

        # And process exit
        index = await child.expect(
            [r"Process exited with code 0", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see clean exit"
        print("✓ Process exited cleanly")

    finally:
        if child.isalive():
            child.close(force=True)
