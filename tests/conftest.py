"""
Shared pytest fixtures for climux functional tests.

These fixtures provide:
- Isolated test environments with unique sockets and temp directories
- Real ClimuxServer instances running in background tasks
- Process factories for creating test processes
- Automatic cleanup of all resources
- Support for pytest-xdist parallel execution
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import subprocess
import sys
import time
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from climux import ClimuxClient, ClimuxServer


@pytest.fixture
def temp_socket_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for sockets."""
    socket_dir = tmp_path / "sockets"
    socket_dir.mkdir(parents=True, exist_ok=True)
    return socket_dir


@pytest.fixture
def unique_socket_path(temp_socket_dir: Path, worker_id: str) -> Path:
    """
    Generate a unique socket path for each test.

    The worker_id is provided by pytest-xdist for parallel execution.
    """
    # Use worker_id to ensure uniqueness in parallel tests
    socket_name = f"test_{os.getpid()}_{worker_id}.sock"
    return temp_socket_dir / socket_name


@pytest_asyncio.fixture
async def climux_server(
    unique_socket_path: Path,
) -> AsyncGenerator[ClimuxServer, None]:
    """
    Start a ClimuxServer instance for testing.

    Yields the server instance and ensures cleanup on test completion.
    """
    server = ClimuxServer(unique_socket_path)

    # Start server in background task
    server_task = asyncio.create_task(server.start())

    # Wait for socket to be created (max 2 seconds)
    for _ in range(40):
        if unique_socket_path.exists():
            break
        await asyncio.sleep(0.05)
    else:
        server_task.cancel()
        pytest.fail("Server socket was not created in time")

    try:
        yield server
    finally:
        # Ensure cleanup
        await server.shutdown()
        server_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await server_task

        # Verify cleanup
        assert not unique_socket_path.exists(), "Socket file was not cleaned up"

        # Check for PID journal cleanup
        pid_journal = (
            unique_socket_path.parent / f"climux_pids_{unique_socket_path.stem}.json"
        )
        assert not pid_journal.exists(), "PID journal was not cleaned up"


@pytest_asyncio.fixture
async def climux_client(
    climux_server: ClimuxServer,
    unique_socket_path: Path,
) -> ClimuxClient:
    """
    Create a ClimuxClient connected to the test server.
    """
    return ClimuxClient(unique_socket_path)


@pytest.fixture
def echo_script(tmp_path: Path) -> Path:
    """Create a simple echo script for testing."""
    script = tmp_path / "echo.py"
    script.write_text("""
import sys
print("Echo started", flush=True)
for line in sys.stdin:
    print(f"Echo: {line.strip()}", flush=True)
""")
    return script


@pytest.fixture
def counter_script(tmp_path: Path) -> Path:
    """Create a script that counts and outputs numbers."""
    script = tmp_path / "counter.py"
    script.write_text("""
import time
import sys

count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1

print(f"Counting to {count}", flush=True)
for i in range(1, count + 1):
    print(f"Count: {i}", flush=True)
    if i < count:
        time.sleep(delay)
print("Done counting", flush=True)
""")
    return script


@pytest.fixture
def error_script(tmp_path: Path) -> Path:
    """Create a script that writes to stderr and exits with error."""
    script = tmp_path / "error.py"
    script.write_text("""
import sys
print("Starting", flush=True)
print("Error occurred!", file=sys.stderr, flush=True)
sys.exit(1)
""")
    return script


@pytest.fixture
def long_running_script(tmp_path: Path) -> Path:
    """Create a long-running script for testing stop/restart."""
    script = tmp_path / "long_running.py"
    script.write_text("""
import signal
import sys
import time

def handle_signal(signum, frame):
    print(f"Received signal {signum}", flush=True)
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_signal)

print("Long running process started", flush=True)
while True:
    print("Still running...", flush=True)
    time.sleep(1)
""")
    return script


@pytest.fixture
def slow_startup_script(tmp_path: Path) -> Path:
    """Create a script that takes time to start up."""
    script = tmp_path / "slow_startup.py"
    script.write_text("""
import time
import sys

print("Starting up...", flush=True)
time.sleep(0.5)
print("Ready!", flush=True)
time.sleep(0.5)
print("Shutting down...", flush=True)
""")
    return script


class ProcessFactory:
    """Factory for creating test processes with common configurations."""

    def __init__(self, client: ClimuxClient):
        self.client = client
        self.created_processes: list[int] = []

    async def create(
        self,
        command: list[str],
        name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a process and track it for cleanup."""
        params = {
            "command": command,
            "name": name or f"test-process-{len(self.created_processes)}",
            **kwargs,
        }
        result = await self.client.request("start", params)
        self.created_processes.append(result["id"])
        return result

    async def cleanup(self) -> None:
        """Stop all created processes."""
        for process_id in self.created_processes:
            try:
                await self.client.request("stop", {"id": process_id})
            except Exception:
                pass  # Process might already be stopped


@pytest_asyncio.fixture
async def process_factory(
    climux_client: ClimuxClient,
) -> AsyncGenerator[ProcessFactory, None]:
    """
    Factory for creating test processes with automatic cleanup.
    """
    factory = ProcessFactory(climux_client)
    try:
        yield factory
    finally:
        await factory.cleanup()


@pytest.fixture
def assert_process_cleanup():
    """
    Fixture to verify that all processes are cleaned up after tests.

    This checks for any lingering Python processes that might be test artifacts.
    """
    # Get initial Python processes
    import psutil

    initial_pids = set()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if "python" in proc.info["name"].lower():
                cmdline = proc.info.get("cmdline", [])
                if cmdline and any("test" in str(arg) for arg in cmdline):
                    initial_pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    yield

    # Check for new Python processes after test
    final_pids = set()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if "python" in proc.info["name"].lower():
                cmdline = proc.info.get("cmdline", [])
                if cmdline and any("test" in str(arg) for arg in cmdline):
                    final_pids.add(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    leaked_pids = final_pids - initial_pids
    if leaked_pids:
        # Try to clean up leaked processes
        for pid in leaked_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        pytest.fail(f"Test leaked processes with PIDs: {leaked_pids}")


@pytest.fixture
def worker_id(request):
    """
    Get the pytest-xdist worker ID for parallel test execution.

    Returns 'master' if not running in parallel.
    """
    return getattr(request.config, "workerinput", {}).get("workerid", "master")


# Markers for different test categories
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "stress: marks tests as stress tests")


# Enhanced fixtures for server lifecycle testing


@pytest_asyncio.fixture
async def managed_server(
    unique_socket_path: Path,
) -> AsyncGenerator[dict[str, Any], None]:
    """
    Advanced fixture for testing server lifecycle management.

    Provides fine-grained control over server state and lifecycle,
    including the ability to start/stop server and verify state.

    Yields a dict with:
        - socket_path: Path to the socket
        - start_server: Coroutine to start server
        - stop_server: Coroutine to stop server
        - is_running: Function to check if server is running
        - get_server: Function to get server instance (if running)
    """
    server: ClimuxServer | None = None
    server_task: asyncio.Task[None] | None = None

    async def start_server() -> ClimuxServer:
        nonlocal server, server_task
        if server is not None:
            raise RuntimeError("Server already running")

        server = ClimuxServer(unique_socket_path)
        server_task = asyncio.create_task(server.start())

        # Wait for socket
        for _ in range(40):
            if unique_socket_path.exists():
                break
            await asyncio.sleep(0.05)
        else:
            server_task.cancel()
            raise RuntimeError("Server failed to start")

        return server

    async def stop_server() -> None:
        nonlocal server, server_task
        if server is None:
            return

        await server.shutdown()
        if server_task:
            server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await server_task

        server = None
        server_task = None

    def is_running() -> bool:
        return server is not None and unique_socket_path.exists()

    def get_server() -> ClimuxServer | None:
        return server

    try:
        yield {
            "socket_path": unique_socket_path,
            "start_server": start_server,
            "stop_server": stop_server,
            "is_running": is_running,
            "get_server": get_server,
        }
    finally:
        # Cleanup any running server
        await stop_server()


class ServerController:
    """Test utility for controlling server lifecycle in tests."""

    def __init__(self, socket_path: Path):
        self.socket_path = socket_path
        self.process: subprocess.Popen[bytes] | None = None

    def start_server_subprocess(
        self, args: list[str] | None = None
    ) -> subprocess.Popen[bytes]:
        """Start server as a real subprocess (like a user would)."""
        if args is None:
            args = []

        cmd = [
            sys.executable,
            "climux.py",
            "-S",
            str(self.socket_path),
            "server",
        ] + args
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent.parent,  # Project root
        )

        # Wait for socket to appear
        for _ in range(50):
            if self.socket_path.exists():
                break
            time.sleep(0.1)
        else:
            self.stop_server_subprocess()
            raise RuntimeError("Server subprocess failed to create socket")

        return self.process

    def stop_server_subprocess(self) -> None:
        """Stop the server subprocess."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
            self.process = None

    def run_client_command(self, args: list[str]) -> tuple[int, str, str]:
        """Run a client command against the server."""
        cmd = [sys.executable, "climux.py", "-S", str(self.socket_path)] + args
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        return result.returncode, result.stdout, result.stderr

    def is_server_running(self) -> bool:
        """Check if server process is running."""
        return self.process is not None and self.process.poll() is None


@pytest.fixture
def server_controller(
    unique_socket_path: Path,
) -> Generator[ServerController, None, None]:
    """
    Fixture providing a ServerController for subprocess-based testing.

    This allows testing the real CLI behavior including implicit server start.
    """
    controller = ServerController(unique_socket_path)
    try:
        yield controller
    finally:
        controller.stop_server_subprocess()
        # Clean up socket if left behind
        if unique_socket_path.exists():
            unique_socket_path.unlink()


@pytest.fixture
def cli_runner(unique_socket_path: Path) -> Generator[Any, None, None]:
    """
    Fixture for running CLI commands with automatic server management.

    This simulates real user behavior where server might start implicitly.
    """
    processes: list[subprocess.Popen[bytes]] = []

    def run(args: list[str], check_server: bool = True) -> tuple[int, str, str]:
        """Run a climux command."""
        cmd = [sys.executable, "climux.py", "-S", str(unique_socket_path)] + args

        # Check if this might start a server
        if check_server and args and args[0] != "server":
            # Give any implicit server time to start
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            # Track any server that might have been started
            if unique_socket_path.exists():
                # Server was started implicitly
                pass
        else:
            # For explicit server start, use Popen
            if args and args[0] == "server":
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=Path(__file__).parent.parent,
                )
                processes.append(proc)
                # Wait for socket
                for _ in range(50):
                    if unique_socket_path.exists():
                        break
                    time.sleep(0.1)
                return 0, "", ""
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=Path(__file__).parent.parent,
                )

        return result.returncode, result.stdout, result.stderr

    try:
        yield run
    finally:
        # Cleanup any processes
        for proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # Clean up socket
        if unique_socket_path.exists():
            unique_socket_path.unlink()
