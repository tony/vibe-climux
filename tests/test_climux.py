"""
Functional tests for climux process manager.

These tests verify the complete functionality of climux including:
- Process lifecycle management (start, stop, restart)
- Input/output handling
- Logging and buffering
- Error handling and recovery
- Concurrent process management
"""

import asyncio
import sys
from pathlib import Path

import pytest
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).parent.parent))

from climux import ClimuxClient, ClimuxServer


class TestBasicOperations:
    """Test basic server and process operations."""
    
    @pytest.mark.asyncio
    async def test_server_ping(self, climux_client: ClimuxClient):
        """Test that server responds to ping."""
        result = await climux_client.request("ping")
        assert result == "pong"
    
    @pytest.mark.asyncio
    async def test_empty_process_list(self, climux_client: ClimuxClient):
        """Test listing processes when none are running."""
        result = await climux_client.request("list")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_start_simple_process(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test starting a simple process."""
        result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "3", "0.1"],
            "name": "test-counter",
        })
        
        assert result["id"] == 1
        assert result["name"] == "test-counter"
        assert result["status"] == "running"
        assert result["pid"] is not None
        
        # Wait for process to complete
        await asyncio.sleep(0.5)
        
        # Check that process appears in list
        processes = await climux_client.request("list")
        assert len(processes) == 1
        assert processes[0]["id"] == 1
        assert processes[0]["status"] == "exited"
    
    @pytest.mark.asyncio
    async def test_process_with_custom_name(
        self,
        climux_client: ClimuxClient,
        echo_script: Path,
    ):
        """Test that custom process names work correctly."""
        result = await climux_client.request("start", {
            "command": [sys.executable, str(echo_script)],
            "name": "my-echo-process",
        })
        
        assert result["name"] == "my-echo-process"
        
        processes = await climux_client.request("list")
        assert processes[0]["name"] == "my-echo-process"


class TestProcessLifecycle:
    """Test process lifecycle management."""
    
    @pytest.mark.asyncio
    async def test_stop_running_process(
        self,
        climux_client: ClimuxClient,
        long_running_script: Path,
    ):
        """Test stopping a running process."""
        # Start process
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(long_running_script)],
            "name": "long-runner",
        })
        process_id = start_result["id"]
        
        # Verify it's running
        await asyncio.sleep(0.1)
        processes = await climux_client.request("list")
        assert processes[0]["status"] == "running"
        
        # Stop the process
        stop_result = await climux_client.request("stop", {"id": process_id})
        assert stop_result["status"] == "stopped"
        assert stop_result["id"] == process_id
        
        # Verify it's stopped
        await asyncio.sleep(0.1)
        processes = await climux_client.request("list")
        assert processes[0]["status"] == "exited"
    
    @pytest.mark.asyncio
    async def test_restart_process(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test restarting a process."""
        # Start process
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "2", "0.1"],
            "name": "restartable",
        })
        process_id = start_result["id"]
        original_pid = start_result["pid"]
        
        # Wait for it to complete
        await asyncio.sleep(0.3)
        
        # Restart it
        restart_result = await climux_client.request("restart", {"id": process_id})
        assert restart_result["id"] == process_id
        assert restart_result["status"] == "running"
        assert restart_result["pid"] != original_pid  # Should have new PID
        
        # Verify it's running with new PID
        processes = await climux_client.request("list")
        assert processes[0]["pid"] == restart_result["pid"]
    
    @pytest.mark.asyncio
    async def test_stop_nonexistent_process(self, climux_client: ClimuxClient):
        """Test stopping a process that doesn't exist."""
        with pytest.raises(RuntimeError, match="Process 999 not found"):
            await climux_client.request("stop", {"id": 999})
    
    @pytest.mark.asyncio
    async def test_restart_nonexistent_process(self, climux_client: ClimuxClient):
        """Test restarting a process that doesn't exist."""
        with pytest.raises(RuntimeError, match="Process 999 not found"):
            await climux_client.request("restart", {"id": 999})


class TestInputOutput:
    """Test process input/output handling."""
    
    @pytest.mark.asyncio
    async def test_send_input_to_process(
        self,
        climux_client: ClimuxClient,
        echo_script: Path,
    ):
        """Test sending input to a process."""
        # Start echo process
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(echo_script)],
            "name": "echo-test",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.1)  # Let process start
        
        # Send input
        send_result = await climux_client.request("send", {
            "id": process_id,
            "data": "Hello, World!",
        })
        assert send_result["status"] == "sent"
        
        await asyncio.sleep(0.1)  # Let process handle input
        
        # Check logs for echoed output
        logs = await climux_client.request("logs", {"id": process_id})
        log_contents = [log["content"] for log in logs]
        assert "Echo started" in log_contents
        assert "Echo: Hello, World!" in log_contents
    
    @pytest.mark.asyncio
    async def test_capture_stdout_stderr(
        self,
        climux_client: ClimuxClient,
        error_script: Path,
    ):
        """Test that both stdout and stderr are captured."""
        # Start process that writes to both streams
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(error_script)],
            "name": "error-test",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.2)  # Let process complete
        
        # Get logs
        logs = await climux_client.request("logs", {"id": process_id})
        
        # Check for both stdout and stderr
        stdout_logs = [log for log in logs if log["source"] == "stdout"]
        stderr_logs = [log for log in logs if log["source"] == "stderr"]
        
        assert any("Starting" in log["content"] for log in stdout_logs)
        assert any("Error occurred!" in log["content"] for log in stderr_logs)
    
    @pytest.mark.asyncio
    async def test_send_input_to_stopped_process(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test that sending input to a stopped process fails gracefully."""
        # Start and let process complete
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "1", "0.1"],
            "name": "quick-exit",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.3)  # Let process complete
        
        # Try to send input
        with pytest.raises(RuntimeError, match="Failed to send input"):
            await climux_client.request("send", {
                "id": process_id,
                "data": "This should fail",
            })


class TestLogging:
    """Test logging and buffering functionality."""
    
    @pytest.mark.asyncio
    async def test_get_logs_with_limit(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test getting logs with a line limit."""
        # Start process that generates multiple log lines
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "10", "0.05"],
            "name": "many-logs",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.7)  # Let process complete
        
        # Get limited logs
        logs = await climux_client.request("logs", {
            "id": process_id,
            "lines": 5,
        })
        
        assert len(logs) == 5
        # Should get the last 5 lines
        assert "Done counting" in logs[-1]["content"]
    
    @pytest.mark.asyncio
    async def test_snapshot_default_lines(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test snapshot with default number of lines."""
        # Start process
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "30", "0.01"],
            "name": "snapshot-test",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.5)  # Let process complete
        
        # Get snapshot (default 25 lines)
        snapshot = await climux_client.request("snapshot", {"id": process_id})
        
        assert len(snapshot) == 25  # Default SNAPSHOT_DEFAULT_LINES
    
    @pytest.mark.asyncio
    async def test_snapshot_custom_lines(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test snapshot with custom number of lines."""
        # Start process
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "20", "0.01"],
            "name": "snapshot-custom",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.3)  # Let process complete
        
        # Get snapshot with custom lines
        snapshot = await climux_client.request("snapshot", {
            "id": process_id,
            "lines": 10,
        })
        
        assert len(snapshot) == 10
    
    @pytest.mark.asyncio
    async def test_log_buffer_limit(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test that log buffer respects max_log_lines setting."""
        # Start process with small buffer
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "20", "0.01"],
            "name": "limited-buffer",
            "max_log_lines": 10,
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.3)  # Let process complete
        
        # Get all logs
        logs = await climux_client.request("logs", {"id": process_id})
        
        # Should only have last 10 lines due to buffer limit
        assert len(logs) <= 10


class TestConcurrency:
    """Test concurrent process management."""
    
    @pytest.mark.asyncio
    async def test_multiple_processes(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
        echo_script: Path,
        process_factory,
    ):
        """Test managing multiple processes simultaneously."""
        # Start multiple processes
        proc1 = await process_factory.create(
            [sys.executable, str(counter_script), "5", "0.1"],
            name="counter-1",
        )
        proc2 = await process_factory.create(
            [sys.executable, str(echo_script)],
            name="echo-1",
        )
        proc3 = await process_factory.create(
            [sys.executable, str(counter_script), "3", "0.1"],
            name="counter-2",
        )
        
        # Verify all are in list
        processes = await climux_client.request("list")
        assert len(processes) == 3
        
        process_names = {p["name"] for p in processes}
        assert process_names == {"counter-1", "echo-1", "counter-2"}
        
        # Send input to echo process
        await climux_client.request("send", {
            "id": proc2["id"],
            "data": "test message",
        })
        
        await asyncio.sleep(0.1)
        
        # Get logs from each
        for proc_id in [proc1["id"], proc2["id"], proc3["id"]]:
            logs = await climux_client.request("logs", {"id": proc_id})
            assert len(logs) > 0
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(
        self,
        climux_client: ClimuxClient,
        long_running_script: Path,
        process_factory,
    ):
        """Test concurrent operations on multiple processes."""
        # Start multiple long-running processes
        procs = []
        for i in range(5):
            proc = await process_factory.create(
                [sys.executable, str(long_running_script)],
                name=f"concurrent-{i}",
            )
            procs.append(proc)
        
        await asyncio.sleep(0.2)  # Let them start
        
        # Perform concurrent operations
        tasks = []
        
        # Stop some processes
        tasks.append(climux_client.request("stop", {"id": procs[0]["id"]}))
        tasks.append(climux_client.request("stop", {"id": procs[1]["id"]}))
        
        # Restart others
        tasks.append(climux_client.request("restart", {"id": procs[2]["id"]}))
        
        # Send input to another
        tasks.append(climux_client.request("send", {
            "id": procs[3]["id"],
            "data": "test",
        }))
        
        # Get logs from the last one
        tasks.append(climux_client.request("logs", {"id": procs[4]["id"]}))
        
        # Execute all concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify no unexpected exceptions
        for result in results:
            if isinstance(result, Exception):
                raise result


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.mark.asyncio
    async def test_invalid_command(self, climux_client: ClimuxClient):
        """Test starting a process with invalid command."""
        with pytest.raises(RuntimeError, match="Failed to start process"):
            await climux_client.request("start", {
                "command": ["/nonexistent/binary"],
                "name": "invalid",
            })
    
    @pytest.mark.asyncio
    async def test_empty_command(self, climux_client: ClimuxClient):
        """Test starting a process with empty command."""
        with pytest.raises(RuntimeError, match="Command is required"):
            await climux_client.request("start", {
                "command": [],
                "name": "empty",
            })
    
    @pytest.mark.asyncio
    async def test_process_exit_code(
        self,
        climux_client: ClimuxClient,
        error_script: Path,
    ):
        """Test that exit codes are properly captured."""
        # Start process that exits with error
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(error_script)],
            "name": "exit-code-test",
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.2)  # Let process complete
        
        # Check status shows exit code
        processes = await climux_client.request("list")
        process = processes[0]
        
        assert process["status"] == "exited"
        assert process["exit_code"] == 1
    
    @pytest.mark.asyncio
    async def test_working_directory(
        self,
        climux_client: ClimuxClient,
        tmp_path: Path,
    ):
        """Test setting custom working directory."""
        # Create a test directory with a file
        test_dir = tmp_path / "test_cwd"
        test_dir.mkdir()
        test_file = test_dir / "test.txt"
        test_file.write_text("test content")
        
        # Create script that lists files
        script = tmp_path / "list_files.py"
        script.write_text("""
import os
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files: {os.listdir('.')}", flush=True)
""")
        
        # Start process with custom cwd
        start_result = await climux_client.request("start", {
            "command": [sys.executable, str(script)],
            "name": "cwd-test",
            "cwd": str(test_dir),
        })
        process_id = start_result["id"]
        
        await asyncio.sleep(0.2)  # Let process complete
        
        # Check logs show correct working directory
        logs = await climux_client.request("logs", {"id": process_id})
        log_contents = " ".join(log["content"] for log in logs)
        
        assert str(test_dir) in log_contents
        assert "test.txt" in log_contents


class TestCleanup:
    """Test cleanup and resource management."""
    
    @pytest.mark.asyncio
    async def test_server_shutdown_stops_processes(
        self,
        unique_socket_path: Path,
        long_running_script: Path,
    ):
        """Test that server shutdown stops all managed processes."""
        # Start a server
        server = ClimuxServer(unique_socket_path)
        server_task = asyncio.create_task(server.start())
        
        # Wait for server to start
        for _ in range(20):
            if unique_socket_path.exists():
                break
            await asyncio.sleep(0.05)
        
        # Start some processes
        client = ClimuxClient(unique_socket_path)
        proc1 = await client.request("start", {
            "command": [sys.executable, str(long_running_script)],
            "name": "cleanup-test-1",
        })
        proc2 = await client.request("start", {
            "command": [sys.executable, str(long_running_script)],
            "name": "cleanup-test-2",
        })
        
        await asyncio.sleep(0.1)
        
        # Get PIDs
        import psutil
        pids = [proc1["pid"], proc2["pid"]]
        
        # Verify processes are running
        for pid in pids:
            assert psutil.pid_exists(pid)
        
        # Shutdown server
        await server.shutdown()
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task
        
        await asyncio.sleep(0.2)
        
        # Verify processes were stopped
        for pid in pids:
            assert not psutil.pid_exists(pid)
    
    @pytest.mark.asyncio
    async def test_pid_journal_cleanup(
        self,
        unique_socket_path: Path,
        counter_script: Path,
    ):
        """Test that PID journal is properly maintained and cleaned up."""
        pid_journal = unique_socket_path.parent / f"climux_pids_{unique_socket_path.stem}.json"
        
        # Start server
        server = ClimuxServer(unique_socket_path)
        server_task = asyncio.create_task(server.start())
        
        # Wait for server
        for _ in range(20):
            if unique_socket_path.exists():
                break
            await asyncio.sleep(0.05)
        
        client = ClimuxClient(unique_socket_path)
        
        # Start a process
        proc = await client.request("start", {
            "command": [sys.executable, str(counter_script), "2", "0.1"],
            "name": "journal-test",
        })
        
        await asyncio.sleep(0.05)
        
        # Check journal exists and contains PID
        assert pid_journal.exists()
        journal_data = json.loads(pid_journal.read_text())
        assert str(proc["id"]) in journal_data
        assert journal_data[str(proc["id"])] == proc["pid"]
        
        # Stop process
        await client.request("stop", {"id": proc["id"]})
        await asyncio.sleep(0.1)
        
        # Journal should be updated
        journal_data = json.loads(pid_journal.read_text())
        assert str(proc["id"]) not in journal_data or journal_data[str(proc["id"])] is None
        
        # Shutdown server
        await server.shutdown()
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task
        
        # Journal should be cleaned up
        assert not pid_journal.exists()


@pytest.mark.slow
class TestStress:
    """Stress tests for climux."""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_many_processes(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
        process_factory,
    ):
        """Test handling many concurrent processes."""
        num_processes = 50
        
        # Start many processes
        tasks = []
        for i in range(num_processes):
            tasks.append(process_factory.create(
                [sys.executable, str(counter_script), "2", "0.01"],
                name=f"stress-{i}",
            ))
        
        procs = await asyncio.gather(*tasks)
        
        # Verify all started
        processes = await climux_client.request("list")
        assert len(processes) == num_processes
        
        # Wait for completion
        await asyncio.sleep(0.5)
        
        # All should be exited
        processes = await climux_client.request("list")
        for proc in processes:
            assert proc["status"] == "exited"
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_rapid_restart(
        self,
        climux_client: ClimuxClient,
        counter_script: Path,
    ):
        """Test rapidly restarting a process."""
        # Start process
        proc = await climux_client.request("start", {
            "command": [sys.executable, str(counter_script), "1", "0.01"],
            "name": "rapid-restart",
        })
        process_id = proc["id"]
        
        # Rapidly restart
        for _ in range(20):
            await climux_client.request("restart", {"id": process_id})
            await asyncio.sleep(0.05)
        
        # Process should still be manageable
        processes = await climux_client.request("list")
        assert len(processes) == 1
        assert processes[0]["id"] == process_id