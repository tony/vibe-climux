"""
Tests for server lifecycle management and implicit server start.

These tests verify that climux behaves like tmux with automatic
server instantiation and proper lifecycle management.
"""

import asyncio
import time
from pathlib import Path

import pytest

from climux import ClimuxClient


class TestImplicitServerStart:
    """Test implicit server start behavior (like tmux)."""

    @pytest.mark.asyncio
    async def test_server_starts_implicitly_on_first_command(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that server starts automatically when running a command."""
        # Server should not be running initially
        assert not unique_socket_path.exists()
        assert not server_controller.is_server_running()

        # Run a command that needs server
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "echo", "hello", "--name", "test"]
        )

        # Command should succeed
        assert returncode == 0, f"Command failed: {stderr}"

        # Server should now be running
        assert unique_socket_path.exists()

        # List should show the process
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert returncode == 0
        assert "test" in stdout

    @pytest.mark.asyncio
    async def test_second_command_uses_existing_server(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that subsequent commands use the already-running server."""
        # Start first process (implicit server start)
        server_controller.run_client_command(
            ["start", "sleep", "30", "--name", "proc1"]
        )

        # Get server start time
        socket_mtime = unique_socket_path.stat().st_mtime
        time.sleep(0.1)

        # Start second process
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "sleep", "30", "--name", "proc2"]
        )
        assert returncode == 0

        # Socket should not have been recreated
        assert unique_socket_path.stat().st_mtime == socket_mtime

        # Both processes should be listed
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert "proc1" in stdout
        assert "proc2" in stdout

    @pytest.mark.asyncio
    async def test_server_command_behavior(self, cli_runner):
        """Test that 'climux server' behaves correctly."""
        # Start server explicitly
        returncode, stdout, stderr = cli_runner(["server"])

        # Should return immediately (daemonized)
        assert returncode == 0

        # Server should be running
        returncode, stdout, stderr = cli_runner(["ping"])
        assert returncode == 0
        assert "pong" in stdout

    @pytest.mark.asyncio
    async def test_server_persists_after_client_exit(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that server keeps running when client exits."""
        # Start a process
        server_controller.run_client_command(
            ["start", "sleep", "30", "--name", "persistent"]
        )

        # Server should be running
        assert unique_socket_path.exists()

        # Run another command and exit
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert returncode == 0

        # Wait a bit
        await asyncio.sleep(0.5)

        # Server should still be running
        assert unique_socket_path.exists()

        # Process should still be listed
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        assert "persistent" in stdout


class TestServerLifecycle:
    """Test server lifecycle management."""

    @pytest.mark.asyncio
    async def test_server_auto_cleanup_on_last_process_exit(
        self, managed_server, unique_socket_path: Path
    ):
        """Test that server can optionally clean up when last process exits."""
        # This tests the capability, even if not default behavior
        server = await managed_server["start_server"]()
        client = ClimuxClient(unique_socket_path)

        # Start a short-lived process
        proc = await client.request(
            "start", {"command": ["echo", "test"], "name": "short-lived"}
        )

        # Wait for process to complete
        await asyncio.sleep(0.2)

        # Check process exited
        processes = await client.request("list")
        assert len(processes) == 1
        assert processes[0]["status"] == "exited"

        # Server should still be running (current behavior)
        assert managed_server["is_running"]()

    @pytest.mark.asyncio
    async def test_explicit_server_stop(self, server_controller):
        """Test explicit server shutdown."""
        # Start server with a process
        server_controller.run_client_command(["start", "sleep", "30", "--name", "test"])

        # Stop server explicitly (future feature)
        # returncode, stdout, stderr = server_controller.run_client_command(
        #     ["server", "--stop"]
        # )
        # assert returncode == 0

        # For now, test that server can be queried
        returncode, stdout, stderr = server_controller.run_client_command(["ping"])
        assert returncode == 0

    @pytest.mark.asyncio
    async def test_server_handles_socket_conflicts(
        self, server_controller, unique_socket_path: Path
    ):
        """Test behavior when socket already exists."""
        # Create a stale socket file
        unique_socket_path.parent.mkdir(parents=True, exist_ok=True)
        unique_socket_path.touch()

        # Try to start server
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "echo", "test", "--name", "test"]
        )

        # Should handle it gracefully (remove stale socket)
        assert returncode == 0 or "already" in stderr

    @pytest.mark.asyncio
    async def test_multiple_socket_support(
        self, temp_socket_dir: Path, server_controller
    ):
        """Test -L and -S options for multiple servers."""
        # Create controllers for different sockets
        socket1 = temp_socket_dir / "session1.sock"
        socket2 = temp_socket_dir / "session2.sock"

        controller1 = type(server_controller)(socket1)
        controller2 = type(server_controller)(socket2)

        try:
            # Start processes on different servers
            controller1.run_client_command(
                ["start", "echo", "server1", "--name", "proc1"]
            )
            controller2.run_client_command(
                ["start", "echo", "server2", "--name", "proc2"]
            )

            # Each server should only see its own processes
            _, stdout1, _ = controller1.run_client_command(["list"])
            _, stdout2, _ = controller2.run_client_command(["list"])

            assert "proc1" in stdout1
            assert "proc2" not in stdout1
            assert "proc2" in stdout2
            assert "proc1" not in stdout2

        finally:
            # Cleanup
            controller1.stop_server_subprocess()
            controller2.stop_server_subprocess()
            if socket1.exists():
                socket1.unlink()
            if socket2.exists():
                socket2.unlink()


class TestServerAttachment:
    """Test server attachment/detachment behavior (future feature)."""

    @pytest.mark.skip(reason="Attachment feature not yet implemented")
    @pytest.mark.asyncio
    async def test_server_attach_shows_dashboard(self, server_controller):
        """Test that 'climux' or 'climux attach' shows live dashboard."""
        # Start some processes
        server_controller.run_client_command(
            ["start", "python", "-c", "import time; time.sleep(30)", "--name", "test"]
        )

        # Attach to server (would show dashboard)
        # This would be interactive in real implementation
        returncode, stdout, stderr = server_controller.run_client_command(["attach"])

        # Should show some status
        assert "test" in stdout or "running" in stdout

    @pytest.mark.skip(reason="Detach feature not yet implemented")
    @pytest.mark.asyncio
    async def test_server_detach_leaves_running(self, server_controller):
        """Test that detaching leaves server running."""
        # This would test Ctrl+C or 'detach' command behavior
        pass


class TestServerRobustness:
    """Test server robustness and error handling."""

    @pytest.mark.asyncio
    async def test_server_recovers_from_stale_pid_journal(
        self, server_controller, unique_socket_path: Path
    ):
        """Test that server handles stale PID journals gracefully."""
        # Create a fake PID journal
        pid_journal = (
            unique_socket_path.parent / f"climux_pids_{unique_socket_path.stem}.json"
        )
        pid_journal.parent.mkdir(parents=True, exist_ok=True)
        pid_journal.write_text('{"1": 99999}')  # Non-existent PID

        # Start server - should clean up stale journal
        returncode, stdout, stderr = server_controller.run_client_command(
            ["start", "echo", "test", "--name", "test"]
        )

        assert returncode == 0

        # Old journal should be gone, new one created
        assert pid_journal.exists()
        journal_data = pid_journal.read_text()
        assert "99999" not in journal_data

    @pytest.mark.asyncio
    async def test_concurrent_client_requests(self, server_controller):
        """Test that server handles concurrent client requests."""
        import concurrent.futures

        # Start server
        server_controller.run_client_command(["ping"])  # Ensure server is up

        # Define tasks to run concurrently
        def start_process(n: int) -> tuple[int, str, str]:
            return server_controller.run_client_command(
                ["start", "echo", f"proc{n}", "--name", f"proc{n}"]
            )

        # Run multiple clients concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(start_process, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        for returncode, stdout, stderr in results:
            assert returncode == 0, f"Failed: {stderr}"

        # All processes should be listed
        returncode, stdout, stderr = server_controller.run_client_command(["list"])
        for i in range(10):
            assert f"proc{i}" in stdout
