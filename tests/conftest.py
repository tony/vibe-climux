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
import os
import signal
import sys
from collections.abc import AsyncGenerator
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
