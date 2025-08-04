"""
Event-based test fixtures for real-time log streaming.

This module provides robust fixtures that use asyncio.Event for
synchronization instead of sleep-based timing.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio

from climux import ClimuxClient, ClimuxServer, LogEntry, ManagedProcess


class EventBasedLogMonitor:
    """Monitors logs with event-based synchronization."""

    def __init__(self):
        self.logs: list[LogEntry] = []
        self.events: dict[str, asyncio.Event] = {}
        self.content_events: dict[str, asyncio.Event] = {}
        self._tasks: list[asyncio.Task] = []

    def add_content_trigger(self, content: str) -> asyncio.Event:
        """Add an event that triggers when specific content is logged."""
        event = asyncio.Event()
        self.content_events[content] = event
        return event

    async def monitor_process(self, process: ManagedProcess) -> None:
        """Start monitoring a process's logs."""
        queue = await process.tail_logs()
        task = asyncio.create_task(self._collect_logs(queue))
        self._tasks.append(task)

    async def _collect_logs(self, queue: asyncio.Queue[LogEntry | None]) -> None:
        """Collect logs from queue and trigger events."""
        while True:
            try:
                entry = await queue.get()
                if entry is None:  # Process ended
                    break

                self.logs.append(entry)

                # Check content triggers
                for content, event in self.content_events.items():
                    if content in entry.content:
                        event.set()

            except asyncio.CancelledError:
                break

    async def wait_for_content(self, content: str, timeout: float = 2.0) -> None:
        """Wait for specific content to appear in logs."""
        event = self.add_content_trigger(content)
        await asyncio.wait_for(event.wait(), timeout=timeout)

    async def cleanup(self) -> None:
        """Clean up monitoring tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)


@pytest_asyncio.fixture
async def event_monitor() -> AsyncGenerator[EventBasedLogMonitor, None]:
    """Fixture providing event-based log monitoring."""
    monitor = EventBasedLogMonitor()
    yield monitor
    await monitor.cleanup()


@pytest_asyncio.fixture
async def server_with_events(
    tmp_path,
) -> AsyncGenerator[tuple[ClimuxServer, asyncio.Event], None]:
    """Server fixture with startup event."""
    socket_path = tmp_path / "test.sock"
    ready_event = asyncio.Event()

    class TestServer(ClimuxServer):
        async def start(self) -> None:
            await super().start()
            ready_event.set()  # Signal server is ready

    server = TestServer(socket_path)
    server_task = asyncio.create_task(server.start())

    # Wait for server to be ready
    await asyncio.wait_for(ready_event.wait(), timeout=5.0)

    try:
        yield server, ready_event
    finally:
        await server.shutdown()
        server_task.cancel()
        await asyncio.gather(server_task, return_exceptions=True)


class TestEventBasedStreaming:
    """Test real-time streaming with event synchronization."""

    @pytest.mark.asyncio
    async def test_event_based_monitoring(
        self,
        climux_server,
        climux_client: ClimuxClient,
        event_monitor: EventBasedLogMonitor,
    ):
        """Test monitoring with events instead of sleep."""
        unique_msg = f"event_test_{uuid.uuid4().hex[:8]}"

        # Start process
        result = await climux_client.request(
            "start",
            {
                "command": ["python", "-c", f"print('{unique_msg}', flush=True)"],
                "name": "event-test",
            },
        )
        process_id = result["id"]

        # Start monitoring BEFORE expecting output
        process = climux_server.processes[process_id]
        await event_monitor.monitor_process(process)

        # Wait for specific content
        await event_monitor.wait_for_content(unique_msg)

        # Verify it was captured
        assert any(unique_msg in log.content for log in event_monitor.logs)

    @pytest.mark.asyncio
    async def test_multiple_event_triggers(
        self,
        climux_server,
        climux_client: ClimuxClient,
        event_monitor: EventBasedLogMonitor,
    ):
        """Test waiting for multiple specific outputs."""
        messages = [f"msg_{i}_{uuid.uuid4().hex[:4]}" for i in range(3)]

        # Python script that prints messages with delays
        script = ";".join(
            [
                f"print('{msg}', flush=True); import time; time.sleep(0.1)"
                for msg in messages
            ]
        )

        result = await climux_client.request(
            "start", {"command": ["python", "-c", script], "name": "multi-event-test"}
        )

        # Monitor the process
        process = climux_server.processes[result["id"]]
        await event_monitor.monitor_process(process)

        # Wait for all messages in parallel
        events = [event_monitor.add_content_trigger(msg) for msg in messages]
        await asyncio.gather(
            *[asyncio.wait_for(event.wait(), timeout=2.0) for event in events]
        )

        # All messages should be captured
        for msg in messages:
            assert any(msg in log.content for log in event_monitor.logs)

    @pytest.mark.asyncio
    async def test_process_completion_event(
        self,
        climux_server,
        climux_client: ClimuxClient,
        event_monitor: EventBasedLogMonitor,
    ):
        """Test waiting for process completion."""
        exit_event = event_monitor.add_content_trigger("Process exited with code 0")
        output_event = event_monitor.add_content_trigger("done")

        # Start a process that outputs then sleeps briefly
        # This gives us time to attach the monitor
        result = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "print('done', flush=True); import time; time.sleep(0.1)",
                ],
                "name": "completion-test",
            },
        )

        # Monitor it
        process = climux_server.processes[result["id"]]
        await event_monitor.monitor_process(process)

        # Wait for both output and completion
        await asyncio.gather(
            asyncio.wait_for(output_event.wait(), timeout=2.0),
            asyncio.wait_for(exit_event.wait(), timeout=2.0),
        )

        # Should have both output and exit message
        assert any("done" in log.content for log in event_monitor.logs)
        assert any(
            "Process exited with code 0" in log.content for log in event_monitor.logs
        )
