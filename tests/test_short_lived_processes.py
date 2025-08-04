"""
Tests for capturing output from short-lived processes.

This module verifies that output from processes that exit quickly
is properly captured before the exit message is logged.
"""

import asyncio
import uuid

import pytest

from climux import ClimuxClient


class TestShortLivedProcesses:
    """Test output capture from processes that exit immediately."""

    @pytest.mark.asyncio
    async def test_echo_output_captured(self, climux_client: ClimuxClient):
        """Test that echo command output is captured."""
        unique_msg = f"test_echo_{uuid.uuid4().hex[:8]}"

        # Start echo process
        result = await climux_client.request(
            "start", {"command": ["echo", unique_msg], "name": "echo-test"}
        )
        process_id = result["id"]

        # Wait a bit for process to complete
        await asyncio.sleep(0.5)

        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})

        # Extract just the content from logs
        log_contents = [log["content"] for log in logs]

        # Verify echo output appears before exit message
        assert unique_msg in log_contents, (
            f"Echo output '{unique_msg}' not found in logs: {log_contents}"
        )

        # Find positions
        echo_pos = next(
            i for i, content in enumerate(log_contents) if unique_msg in content
        )
        exit_pos = next(
            i for i, content in enumerate(log_contents) if "Process exited" in content
        )

        # Echo output should come before exit message
        assert echo_pos < exit_pos, "Echo output should appear before exit message"

    @pytest.mark.asyncio
    async def test_python_print_captured(self, climux_client: ClimuxClient):
        """Test that Python print output is captured."""
        unique_msg = f"test_python_{uuid.uuid4().hex[:8]}"

        # Python command that prints and exits immediately
        python_cmd = ["python", "-c", f"print('{unique_msg}', flush=True)"]

        result = await climux_client.request(
            "start", {"command": python_cmd, "name": "python-test"}
        )
        process_id = result["id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})
        log_contents = [log["content"] for log in logs]

        # Verify output captured
        assert unique_msg in log_contents, (
            f"Python output not found in logs: {log_contents}"
        )

    @pytest.mark.asyncio
    async def test_multiple_lines_captured(self, climux_client: ClimuxClient):
        """Test that multiple lines from short process are captured."""
        lines = [f"line_{i}_{uuid.uuid4().hex[:4]}" for i in range(5)]

        # Create multi-line output
        python_cmd = [
            "python",
            "-c",
            ";\n".join(f"print('{line}', flush=True)" for line in lines),
        ]

        result = await climux_client.request(
            "start", {"command": python_cmd, "name": "multiline-test"}
        )
        process_id = result["id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})
        log_contents = [log["content"] for log in logs]

        # All lines should be captured
        for line in lines:
            assert line in log_contents, f"Line '{line}' not found in logs"

    @pytest.mark.asyncio
    async def test_stderr_captured(self, climux_client: ClimuxClient):
        """Test that stderr from short process is captured."""
        unique_err = f"test_error_{uuid.uuid4().hex[:8]}"

        python_cmd = [
            "python",
            "-c",
            f"import sys; sys.stderr.write('{unique_err}\\n'); sys.stderr.flush()",
        ]

        result = await climux_client.request(
            "start", {"command": python_cmd, "name": "stderr-test"}
        )
        process_id = result["id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})

        # Check stderr was captured
        stderr_logs = [log for log in logs if log["source"] == "stderr"]
        assert any(unique_err in log["content"] for log in stderr_logs), (
            f"Stderr output not found in logs: {[log['content'] for log in stderr_logs]}"
        )

    @pytest.mark.asyncio
    async def test_exit_code_after_output(self, climux_client: ClimuxClient):
        """Test that exit code is logged after all output."""
        unique_msg = f"final_output_{uuid.uuid4().hex[:8]}"

        # Process that prints then exits with specific code
        python_cmd = ["python", "-c", f"print('{unique_msg}', flush=True); exit(42)"]

        result = await climux_client.request(
            "start", {"command": python_cmd, "name": "exit-code-test"}
        )
        process_id = result["id"]

        # Wait for completion
        await asyncio.sleep(0.5)

        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})

        # Find exit message
        exit_log = next(
            (log for log in logs if "Process exited with code 42" in log["content"]),
            None,
        )
        assert exit_log is not None, "Exit message not found"

        # Verify output appears before exit
        output_logs = [log for log in logs if unique_msg in log["content"]]
        assert output_logs, "Output not found"

        # Compare timestamps
        output_time = output_logs[0]["timestamp"]
        exit_time = exit_log["timestamp"]
        assert output_time <= exit_time, "Output should be logged before exit"
