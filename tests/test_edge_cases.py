"""
Tests for edge cases and error conditions in climux.

These tests cover scenarios like server crashes, permission errors,
and other unusual conditions that might occur in production.
"""

import os
import signal
import tempfile
import time
from pathlib import Path

import pytest


class TestServerCrashRecovery:
    """Test recovery from server crashes."""

    @pytest.mark.asyncio
    async def test_server_restart_after_crash(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that client commands work after server crashes."""
        # Start a process (implicit server start)
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "sleep", "60", "--name", "long-running"]
        )
        assert returncode == 0

        # Verify server is running
        assert unique_socket_path.exists()

        # Find and kill the server process directly (simulate crash)
        # This is a bit hacky but simulates a real crash
        server_pid = None
        for _ in range(10):
            try:
                # Try to find server process by checking if socket is in use
                import psutil

                for proc in psutil.process_iter(["pid", "cmdline"]):
                    cmdline = proc.info.get("cmdline", [])
                    if cmdline and "climux.py" in str(cmdline) and "server" in cmdline:
                        if str(unique_socket_path) in str(cmdline):
                            server_pid = proc.info["pid"]
                            break
                if server_pid:
                    break
            except Exception:
                pass
            time.sleep(0.1)

        if server_pid:
            # Kill server ungracefully (SIGKILL)
            os.kill(server_pid, signal.SIGKILL)
            time.sleep(0.5)

        # Socket might still exist but server is dead
        # Try to run a new command - should start new server
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "echo", "recovery-test", "--name", "recovery"]
        )

        # Should succeed with new server
        assert returncode == 0, f"Failed to recover: {stderr}"

        # List should show the new process (old one might be gone)
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert returncode == 0
        assert "recovery" in stdout

    @pytest.mark.asyncio
    async def test_stale_socket_cleanup(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that stale sockets are cleaned up properly."""
        # Create a stale socket (no server listening)
        unique_socket_path.parent.mkdir(parents=True, exist_ok=True)
        unique_socket_path.touch()

        # Should detect stale socket and start new server
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "echo", "test", "--name", "test"]
        )

        assert returncode == 0, f"Failed with stale socket: {stderr}"

        # Verify server is now running
        returncode, stdout, stderr = server_controller.run_client_command(["ping"])
        assert returncode == 0
        assert "pong" in stdout


class TestSocketOptions:
    """Test -L and -S socket options with implicit start."""

    @pytest.mark.asyncio
    async def test_socket_name_option(self, temp_socket_dir: Path):
        """Test -L option for named sockets."""
        import subprocess
        import sys

        socket_name = "test-session.sock"

        # Use -L option
        cmd = [
            sys.executable,
            "climux.py",
            "-L",
            socket_name,
            "start",
            "echo",
            "test",
            "--name",
            "named-socket-test",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"

        # Check socket was created in temp dir
        expected_socket = Path(tempfile.gettempdir()) / "climux" / socket_name
        assert expected_socket.exists()

        # List using same socket name
        cmd = [sys.executable, "climux.py", "-L", socket_name, "list"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0
        assert "named-socket-test" in result.stdout

        # Cleanup
        if expected_socket.exists():
            # Kill the server
            cmd = [sys.executable, "climux.py", "-L", socket_name, "ping"]
            subprocess.run(cmd, capture_output=True, cwd=Path(__file__).parent.parent)
            expected_socket.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_socket_path_option(self, temp_socket_dir: Path):
        """Test -S option for full socket paths."""
        import subprocess
        import sys

        socket_path = temp_socket_dir / "custom-path.sock"

        # Use -S option
        cmd = [
            sys.executable,
            "climux.py",
            "-S",
            str(socket_path),
            "start",
            "echo",
            "test",
            "--name",
            "custom-path-test",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert socket_path.exists()

        # List using same socket path
        cmd = [sys.executable, "climux.py", "-S", str(socket_path), "list"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0
        assert "custom-path-test" in result.stdout


class TestPermissionErrors:
    """Test handling of permission errors."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.getuid() == 0, reason="Cannot test permissions as root")
    async def test_socket_permission_denied(self, temp_socket_dir: Path):
        """Test graceful handling when socket directory has no write permission."""
        import subprocess
        import sys

        # Create a directory with no write permission
        restricted_dir = temp_socket_dir / "restricted"
        restricted_dir.mkdir(mode=0o555)  # Read and execute only

        socket_path = restricted_dir / "test.sock"

        try:
            # Try to start server in restricted directory
            cmd = [
                sys.executable,
                "climux.py",
                "-S",
                str(socket_path),
                "start",
                "echo",
                "test",
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            # Should fail gracefully
            assert result.returncode != 0
            assert (
                "Failed to start server" in result.stderr
                or "Permission" in result.stderr
            )

        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)

    @pytest.mark.asyncio
    async def test_server_already_running_detection(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that server command detects already running server."""
        # Start a process (implicit server start)
        server_controller.run_client_command(["start", "sleep", "30", "--name", "test"])

        # Try to start server explicitly
        returncode, stdout, stderr = server_controller.run_client_command(["server"])

        # Should detect existing server
        assert "already running" in stdout.lower() or returncode == 0


class TestProcessCleanup:
    """Test process cleanup in edge cases."""

    @pytest.mark.asyncio
    async def test_orphaned_process_cleanup(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that orphaned processes are cleaned up on server restart."""
        # Start a long-running process
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "sleep", "300", "--name", "orphan-test"]
        )
        assert returncode == 0

        # Get the process list to find PID
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert returncode == 0

        # Extract PID from output (format: [1] orphan-test: running (PID: 12345))
        import re

        pid_match = re.search(r"PID: (\d+)", stdout)
        assert pid_match, "Could not find PID in output"
        process_pid = int(pid_match.group(1))

        # Kill server but not the process (simulate partial cleanup failure)
        server_pid = None
        try:
            import psutil

            for proc in psutil.process_iter(["pid", "cmdline"]):
                cmdline = proc.info.get("cmdline", [])
                if cmdline and "climux.py" in str(cmdline) and "server" in cmdline:
                    if str(unique_socket_path) in str(cmdline):
                        server_pid = proc.info["pid"]
                        break
        except Exception:
            pass

        if server_pid:
            os.kill(server_pid, signal.SIGTERM)
            time.sleep(0.5)

        # Process might still be running
        process_still_alive = True
        try:
            os.kill(process_pid, 0)  # Check if process exists
        except ProcessLookupError:
            process_still_alive = False

        # Start new server - should clean up orphaned process via PID journal
        returncode, stdout, stderr = server_controller.run_client_command(["ping"])

        # Give cleanup time to work
        if process_still_alive:
            time.sleep(0.5)

            # Check if process was cleaned up
            try:
                os.kill(process_pid, 0)
                pytest.fail("Orphaned process was not cleaned up")
            except ProcessLookupError:
                pass  # Good, process was cleaned up
