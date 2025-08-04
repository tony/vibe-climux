"""
Minimal test to demonstrate the CLI hanging issue with pipe buffering.

This test will timeout/hang when using normal subprocess pipes
because stdout becomes block-buffered instead of line-buffered.
"""

import asyncio
import sys
from pathlib import Path

import pytest

CLIMUX_PATH = Path(__file__).parent.parent / "climux.py"


@pytest.mark.asyncio
@pytest.mark.timeout(5)  # This test should timeout
async def test_cli_tail_hangs_with_subprocess(climux_server, climux_client):
    """
    This test demonstrates the hanging issue when using subprocess.PIPE
    with the CLI streaming command.
    """
    # First, start a simple process that outputs logs
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-c",
                "import time; print('Started', flush=True); time.sleep(10)",
            ],
            "name": "test_process",
        },
    )
    process_id = result["id"]

    # Now try to tail the logs using subprocess - this will hang
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(CLIMUX_PATH),
        "-S",
        str(climux_server.socket_path),
        "logs",
        "--tail",
        str(process_id),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        # This will hang waiting for output due to pipe buffering
        # The subprocess stdout is block-buffered, not line-buffered
        print("Waiting for first line (this will hang)...")
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=2.0)

        # We won't reach here
        assert b"Started" in line

    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.asyncio
async def test_cli_tail_fixed_with_pexpect(climux_server, climux_client):
    """
    This test shows how pexpect fixes the hanging issue by using
    a pseudo-TTY which forces line-buffered output.
    """
    import pexpect

    # First, start a process that outputs logs AFTER we start tailing
    result = await climux_client.request(
        "start",
        {
            "command": [
                "python",
                "-c",
                "import time; time.sleep(1); print('After tail started', flush=True); time.sleep(5)",
            ],
            "name": "test_process",
        },
    )
    process_id = result["id"]

    # Use pexpect to spawn the CLI with a pseudo-TTY
    child = pexpect.spawn(
        f"{sys.executable} {CLIMUX_PATH} -S {climux_server.socket_path} logs --tail {process_id}",
        encoding="utf-8",
        timeout=5,
    )

    try:
        # This should work because pexpect uses a PTY
        # which makes output line-buffered
        # Looking for pattern: [timestamp] [stdout] After tail started
        index = await child.expect(
            [r"\[.*\] \[stdout\] After tail started", pexpect.TIMEOUT], async_=True
        )

        # Debug: Print what we actually got
        print(f"Index: {index}")
        print(f"Before: {child.before}")
        print(f"After: {child.after}")

        assert index == 0, "Should find 'After tail started' in output"

        # Send Ctrl+C to stop
        child.sendcontrol("c")
        await child.expect(pexpect.EOF, async_=True)

    finally:
        if child.isalive():
            child.close(force=True)
