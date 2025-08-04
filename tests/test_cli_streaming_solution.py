"""
Demonstrates the solution to CLI streaming hanging issue using pexpect.

This test shows that pexpect solves the pipe buffering problem by creating
a pseudo-TTY which forces line-buffered output.

NOTE: These tests have timing issues. See test_high_volume_streaming.py and
test_cli_signal_sync.py for working implementations.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Timing issues - see test_high_volume_streaming.py for working versions"
)

import sys
from pathlib import Path

import pexpect
import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
async def test_cli_streaming_with_pexpect_works(climux_server, climux_client):
    """
    Test that pexpect enables real-time streaming by using a PTY.
    """
    # Start a process that outputs continuously
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",  # Unbuffered for Python
                "-c",
                """import time
for i in range(5):
    print(f'Line {i}', flush=True)
    time.sleep(0.1)
""",
            ],
            "name": "streaming_test",
        },
    )
    process_id = result["id"]

    # Use pexpect to tail the logs with a PTY
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=5,
    )

    try:
        # We should see lines appear in real-time
        for i in range(5):
            index = await child.expect(
                [rf"\[.*\] \[stdout\] Line {i}", pexpect.TIMEOUT], async_=True
            )
            assert index == 0, f"Should see Line {i}"
            print(f"✓ Received Line {i} in real-time")

        # Verify process completes
        index = await child.expect(
            [r"\[.*\] \[system\] Process exited with code 0", pexpect.TIMEOUT],
            async_=True,
        )
        assert index == 0, "Process should exit cleanly"

    finally:
        if child.isalive():
            child.close(force=True)


@pytest.mark.asyncio
async def test_cli_streaming_handles_high_volume(climux_server, climux_client):
    """
    Test that streaming works with high-volume output.
    """
    # Start a process that outputs many lines quickly
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                "for i in range(100): print(f'High volume line {i}', flush=True)",
            ],
            "name": "high_volume_test",
        },
    )
    process_id = result["id"]

    # Use pexpect to tail the logs
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=10,
    )

    try:
        # Verify we can see early, middle, and late lines
        for line_num in [0, 50, 99]:
            index = await child.expect(
                [rf"\[.*\] \[stdout\] High volume line {line_num}", pexpect.TIMEOUT],
                async_=True,
            )
            assert index == 0, f"Should see line {line_num}"
            print(f"✓ Received line {line_num}")

        # Process should complete
        index = await child.expect(
            [r"\[.*\] \[system\] Process exited with code 0", pexpect.TIMEOUT],
            async_=True,
        )
        assert index == 0, "Process should exit cleanly"

    finally:
        if child.isalive():
            child.close(force=True)


@pytest.mark.asyncio
async def test_multiple_cli_streams_simultaneously(climux_server, climux_client):
    """
    Test multiple simultaneous streaming sessions.
    """
    # Start two processes
    proc1 = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                "import time; [print(f'Proc1 line {i}', flush=True) or time.sleep(0.2) for i in range(5)]",
            ],
            "name": "proc1",
        },
    )

    proc2 = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-u",
                "-c",
                "import time; [print(f'Proc2 line {i}', flush=True) or time.sleep(0.2) for i in range(5)]",
            ],
            "name": "proc2",
        },
    )

    # Tail both simultaneously
    child1 = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {proc1['id']}",
        encoding="utf-8",
        timeout=5,
    )

    child2 = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {proc2['id']}",
        encoding="utf-8",
        timeout=5,
    )

    try:
        # Both should work independently
        index1 = await child1.expect(
            [r"\[.*\] \[stdout\] Proc1 line 0", pexpect.TIMEOUT], async_=True
        )
        index2 = await child2.expect(
            [r"\[.*\] \[stdout\] Proc2 line 0", pexpect.TIMEOUT], async_=True
        )

        assert index1 == 0, "Should see proc1 output"
        assert index2 == 0, "Should see proc2 output"

        print("✓ Both streams working simultaneously")

    finally:
        if child1.isalive():
            child1.close(force=True)
        if child2.isalive():
            child2.close(force=True)
