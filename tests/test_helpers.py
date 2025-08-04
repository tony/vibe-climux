"""
Test helpers and debugging utilities for climux tests.

This module provides enhanced debugging capabilities for tests:
- Detailed logging of server/client interactions
- Process state inspection
- Timing diagnostics
- Test isolation verification
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from climux import ClimuxClient, ClimuxServer

# Set up test-specific logger
test_logger = logging.getLogger("climux.test")
test_logger.setLevel(logging.DEBUG)


class DebugClient(ClimuxClient):
    """Enhanced client with debugging capabilities."""

    def __init__(self, socket_path: Path, debug: bool = True):
        super().__init__(socket_path)
        self.debug = debug
        self.request_count = 0
        self.request_history: list[tuple[str, dict[str, Any], Any]] = []

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request with debug logging."""
        self.request_count += 1
        start_time = time.monotonic()

        if self.debug:
            test_logger.debug(
                f"[Request #{self.request_count}] {method} with params: {params}"
            )

        try:
            result = await super().request(method, params)
            elapsed = time.monotonic() - start_time

            if self.debug:
                test_logger.debug(
                    f"[Response #{self.request_count}] {method} completed in {elapsed:.3f}s: {result}"
                )

            self.request_history.append((method, params or {}, result))
            return result

        except Exception as e:
            elapsed = time.monotonic() - start_time
            if self.debug:
                test_logger.error(
                    f"[Error #{self.request_count}] {method} failed after {elapsed:.3f}s: {e}"
                )
            self.request_history.append((method, params or {}, e))
            raise

    def get_last_request(self) -> tuple[str, dict[str, Any], Any]:
        """Get the last request made."""
        if not self.request_history:
            raise ValueError("No requests have been made")
        return self.request_history[-1]

    def clear_history(self) -> None:
        """Clear request history."""
        self.request_history.clear()
        self.request_count = 0


class DebugServer(ClimuxServer):
    """Enhanced server with debugging hooks."""

    def __init__(self, socket_path: Path, debug: bool = True):
        super().__init__(socket_path)
        self.debug = debug
        self.request_log: list[dict[str, Any]] = []
        self.process_events: list[tuple[float, str, dict[str, Any]]] = []

    async def _dispatch_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Dispatch with logging."""
        if self.debug:
            self.request_log.append(
                {"timestamp": time.monotonic(), "request": request.copy()}
            )

        response = await super()._dispatch_request(request)

        if self.debug and "error" not in response:
            self.request_log[-1]["response"] = response.copy()

        return response

    def log_process_event(self, event: str, data: dict[str, Any]) -> None:
        """Log a process lifecycle event."""
        if self.debug:
            self.process_events.append((time.monotonic(), event, data))


@contextlib.asynccontextmanager
async def debug_server(
    socket_path: Path, timeout: float = 2.0
) -> AsyncIterator[DebugServer]:
    """Context manager for a debug server with proper lifecycle."""
    server = DebugServer(socket_path)
    server_task = asyncio.create_task(server.start())

    # Wait for socket with timeout
    start_time = time.monotonic()
    while not socket_path.exists():
        if time.monotonic() - start_time > timeout:
            server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await server_task
            raise TimeoutError(f"Server socket not created within {timeout}s")
        await asyncio.sleep(0.05)

    try:
        yield server
    finally:
        # Ensure proper cleanup
        await server.shutdown()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task

        # Verify cleanup
        if socket_path.exists():
            test_logger.warning(f"Socket {socket_path} still exists after shutdown")


async def wait_for_process_status(
    client: ClimuxClient,
    process_id: int,
    expected_status: str,
    timeout: float = 5.0,
    poll_interval: float = 0.1,
) -> dict[str, Any]:
    """Wait for a process to reach a specific status."""
    start_time = time.monotonic()

    while time.monotonic() - start_time < timeout:
        processes = await client.request("list")
        for proc in processes:
            if proc["id"] == process_id:
                if proc["status"] == expected_status:
                    return proc
                break
        else:
            raise ValueError(f"Process {process_id} not found")

        await asyncio.sleep(poll_interval)

    # Timeout - get final status for error message
    processes = await client.request("list")
    for proc in processes:
        if proc["id"] == process_id:
            raise TimeoutError(
                f"Process {process_id} did not reach status '{expected_status}' "
                f"within {timeout}s. Current status: {proc['status']}"
            )

    raise ValueError(f"Process {process_id} disappeared while waiting")


async def get_process_logs_with_retry(
    client: ClimuxClient,
    process_id: int,
    retries: int = 3,
    delay: float = 0.1,
) -> list[dict[str, Any]]:
    """Get process logs with retry logic for timing issues."""
    for attempt in range(retries):
        try:
            logs = await client.request("logs", {"id": process_id})
            if logs:  # If we got logs, return them
                return logs

            if attempt < retries - 1:
                await asyncio.sleep(delay)
        except Exception as e:
            if attempt == retries - 1:
                raise
            test_logger.debug(f"Retry {attempt + 1} after error: {e}")
            await asyncio.sleep(delay)

    return []


class ProcessMonitor:
    """Monitor process lifecycle for debugging."""

    def __init__(self, client: ClimuxClient):
        self.client = client
        self.snapshots: list[tuple[float, list[dict[str, Any]]]] = []
        self._monitoring = False
        self._task: asyncio.Task[None] | None = None

    async def start(self, interval: float = 0.5) -> None:
        """Start monitoring processes."""
        if self._monitoring:
            return

        self._monitoring = True
        self._task = asyncio.create_task(self._monitor_loop(interval))

    async def stop(self) -> None:
        """Stop monitoring."""
        self._monitoring = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _monitor_loop(self, interval: float) -> None:
        """Monitor loop."""
        while self._monitoring:
            try:
                processes = await self.client.request("list")
                self.snapshots.append((time.monotonic(), processes))
            except Exception as e:
                test_logger.error(f"Monitor error: {e}")

            await asyncio.sleep(interval)

    def get_process_history(self, process_id: int) -> list[dict[str, Any]]:
        """Get history of a specific process."""
        history = []
        for timestamp, processes in self.snapshots:
            for proc in processes:
                if proc["id"] == process_id:
                    history.append({"timestamp": timestamp, **proc})
                    break
        return history


def assert_log_contains(
    logs: list[dict[str, Any]],
    expected_content: str,
    source: str | None = None,
) -> None:
    """Assert that logs contain expected content."""
    for log in logs:
        if source and log.get("source") != source:
            continue
        if expected_content in log.get("content", ""):
            return

    # Not found - provide helpful error message
    log_summary = "\n".join(
        f"  [{log.get('source', 'unknown')}] {log.get('content', '')}"
        for log in logs[-10:]  # Show last 10 logs
    )

    source_msg = f" in source '{source}'" if source else ""
    raise AssertionError(
        f"Expected content '{expected_content}'{source_msg} not found in logs.\n"
        f"Last 10 log entries:\n{log_summary}"
    )


def assert_process_in_list(
    processes: list[dict[str, Any]],
    process_id: int | None = None,
    name: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Assert that a process with given criteria exists in the list."""
    for proc in processes:
        if process_id is not None and proc["id"] != process_id:
            continue
        if name is not None and proc["name"] != name:
            continue
        if status is not None and proc["status"] != status:
            continue
        return proc

    # Not found - provide helpful error message
    criteria = []
    if process_id is not None:
        criteria.append(f"id={process_id}")
    if name is not None:
        criteria.append(f"name='{name}'")
    if status is not None:
        criteria.append(f"status='{status}'")

    process_summary = "\n".join(
        f"  [{p['id']}] {p['name']}: {p['status']}" for p in processes
    )

    raise AssertionError(
        f"No process found matching criteria: {', '.join(criteria)}\n"
        f"Available processes:\n{process_summary}"
    )
