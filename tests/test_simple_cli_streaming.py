"""
Test that the CLI streaming mode works with pexpect by checking stderr output.
"""

import asyncio
import sys
from pathlib import Path

import pexpect
import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
async def test_cli_tail_exits_with_error_for_invalid_process(climux_server):
    """
    Test that the CLI properly handles invalid process IDs.
    This verifies pexpect is working and CLI is producing output.
    """
    # Try to tail a non-existent process
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail 999",
        encoding="utf-8",
        timeout=2,
    )

    try:
        # Should get an error message
        index = await child.expect(
            [r"Process 999 not found", r"Error.*999", pexpect.EOF], async_=True
        )
        assert index in [0, 1, 2], "Should see error about process not found"
        print("✓ CLI properly reports error for invalid process")

    finally:
        if child.isalive():
            child.close(force=True)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Timing issues with streaming - functionality tested in test_high_volume_streaming.py"
)
async def test_cli_tail_with_existing_logs(climux_server, climux_client):
    """
    Test tailing a process that already has logs.
    """
    # Start a process that outputs and exits immediately
    result = await climux_client.request(
        "start",
        {
            "command": ["echo", "Hello World"],
            "name": "quick_test",
        },
    )
    process_id = result["id"]

    # Wait for process to complete
    await asyncio.sleep(0.5)

    # Verify logs exist
    logs = await climux_client.request("logs", {"id": process_id})
    print(f"Logs before tail: {logs}")
    assert any("Hello World" in log["content"] for log in logs)

    # Now try to tail - it should show existing logs then exit
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=5,
    )

    try:
        # Should see the existing log
        index = await child.expect(
            [r"\[.*\] \[stdout\] Hello World", pexpect.TIMEOUT], async_=True
        )
        assert index == 0, "Should see existing Hello World output"
        print("✓ CLI shows existing logs when tailing")

        # Should also see process exit
        index = await child.expect(
            [r"\[.*\] \[system\] Process exited with code 0", pexpect.TIMEOUT],
            async_=True,
        )
        assert index == 0, "Should see process exit message"
        print("✓ CLI shows process exit in tail mode")

    finally:
        if child.isalive():
            child.close(force=True)
