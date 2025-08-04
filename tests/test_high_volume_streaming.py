"""
Test high-volume streaming scenarios with pexpect.
"""

import asyncio
import sys
from pathlib import Path

import pexpect
import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
async def test_high_volume_streaming(climux_server, climux_client):
    """
    Test that CLI streaming handles high-volume output correctly.
    """
    # Start a process that outputs many lines quickly
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                """import time
# Wait a bit before starting
time.sleep(2)

# Output 100 lines rapidly
for i in range(100):
    print(f'High volume line {i:03d}', flush=True)
    if i % 10 == 0:
        time.sleep(0.01)  # Small pause every 10 lines

print('COMPLETED ALL OUTPUT', flush=True)
""",
            ],
            "name": "high_volume_test",
        },
    )
    process_id = result["id"]

    # Start tailing
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=30,
    )

    try:
        # Give streaming a moment to establish
        await asyncio.sleep(1)

        # Check we see early lines
        index = await child.expect(
            [r"High volume line 005", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see early output"
        print("✓ Received early lines")

        # Check we see middle lines
        index = await child.expect(
            [r"High volume line 050", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see middle output"
        print("✓ Received middle lines")

        # Check we see late lines
        index = await child.expect(
            [r"High volume line 095", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see late output"
        print("✓ Received late lines")

        # Check completion
        index = await child.expect(
            [r"COMPLETED ALL OUTPUT", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see completion"
        print("✓ Received completion message")

        # Process should exit
        index = await child.expect(
            [r"Process exited with code 0", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see clean exit"
        print("✓ Process exited cleanly")

    finally:
        if child.isalive():
            child.close(force=True)


@pytest.mark.asyncio
async def test_burst_output_streaming(climux_server, climux_client):
    """
    Test streaming with burst output patterns.
    """
    # Start a process with burst output
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                """import time

# Wait before starting
time.sleep(2)

# Burst 1: 50 lines instantly
print('BURST 1 START', flush=True)
for i in range(50):
    print(f'Burst 1 line {i}', flush=True)
print('BURST 1 END', flush=True)

# Pause
time.sleep(1)

# Burst 2: 50 more lines
print('BURST 2 START', flush=True) 
for i in range(50):
    print(f'Burst 2 line {i}', flush=True)
print('BURST 2 END', flush=True)
""",
            ],
            "name": "burst_test",
        },
    )
    process_id = result["id"]

    # Start tailing
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=15,
    )

    try:
        # Give streaming a moment to establish
        await asyncio.sleep(1)

        # Should see first burst
        index = await child.expect([r"BURST 1 START", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see burst 1 start"

        index = await child.expect([r"BURST 1 END", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see burst 1 end"
        print("✓ Received first burst")

        # Should see second burst after delay
        index = await child.expect([r"BURST 2 START", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see burst 2 start"

        index = await child.expect([r"BURST 2 END", pexpect.TIMEOUT], async_=True)
        assert index == 0, "Should see burst 2 end"
        print("✓ Received second burst")

        # Process should exit
        index = await child.expect(
            [r"Process exited with code 0", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see clean exit"
        print("✓ Process exited cleanly")

    finally:
        if child.isalive():
            child.close(force=True)


@pytest.mark.asyncio
async def test_multiple_simultaneous_streams(climux_server, climux_client):
    """
    Test multiple CLI tail sessions simultaneously.
    """
    # Start two processes
    proc1 = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                """import time
time.sleep(2)  # Wait before starting
for i in range(10):
    print(f'Process 1 message {i}', flush=True)
    time.sleep(0.2)
print('PROCESS 1 DONE', flush=True)
""",
            ],
            "name": "stream_proc1",
        },
    )

    proc2 = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                """import time
time.sleep(2)  # Wait before starting
for i in range(10):
    print(f'Process 2 message {i}', flush=True)
    time.sleep(0.2)
print('PROCESS 2 DONE', flush=True)
""",
            ],
            "name": "stream_proc2",
        },
    )

    # Start two tail sessions
    child1 = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {proc1['id']}",
        encoding="utf-8",
        timeout=10,
    )

    child2 = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {proc2['id']}",
        encoding="utf-8",
        timeout=10,
    )

    try:
        # Give streaming a moment to establish
        await asyncio.sleep(1)

        # Both should receive their respective messages
        index1 = await child1.expect(
            [r"Process 1 message 5", pexpect.TIMEOUT], async_=True
        )
        assert index1 == 0, "Should see process 1 messages"

        index2 = await child2.expect(
            [r"Process 2 message 5", pexpect.TIMEOUT], async_=True
        )
        assert index2 == 0, "Should see process 2 messages"
        print("✓ Both streams receiving independently")

        # Both should complete
        index1 = await child1.expect([r"PROCESS 1 DONE", pexpect.TIMEOUT], async_=True)
        assert index1 == 0, "Process 1 should complete"

        index2 = await child2.expect([r"PROCESS 2 DONE", pexpect.TIMEOUT], async_=True)
        assert index2 == 0, "Process 2 should complete"
        print("✓ Both processes completed")

    finally:
        if child1.isalive():
            child1.close(force=True)
        if child2.isalive():
            child2.close(force=True)
