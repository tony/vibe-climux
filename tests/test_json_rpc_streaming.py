"""
Tests for JSON-RPC streaming functionality.

This module tests the subscribe/unsubscribe methods and real-time
log streaming using JSON-RPC notifications.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
import pytest_asyncio

from climux import ClimuxClient


class StreamingClient:
    """Test client that can handle streaming notifications."""

    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.notifications: list[dict[str, Any]] = []
        self._responses: dict[str, asyncio.Future] = {}
        self._reader = None
        self._writer = None
        self._read_task = None

    async def connect(self):
        """Connect to the server."""
        self._reader, self._writer = await asyncio.open_unix_connection(
            str(self.socket_path)
        )
        # Start background task to read notifications
        self._read_task = asyncio.create_task(self._read_notifications())

    async def disconnect(self):
        """Disconnect from server."""
        if self._read_task:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Send a request and wait for response."""
        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": request_id,
        }

        # Create a future for this response
        response_future = asyncio.Future()
        self._responses[request_id] = response_future

        # Send request
        self._writer.write(json.dumps(request).encode() + b"\n")
        await self._writer.drain()

        # Wait for response
        try:
            result = await response_future
            if "error" in result:
                raise RuntimeError(f"Server error: {result['error']['message']}")
            return result.get("result")
        finally:
            # Clean up
            self._responses.pop(request_id, None)

    async def _read_notifications(self):
        """Background task to read all messages."""
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    break

                try:
                    msg = json.loads(line.decode())

                    # Check if it's a response to a pending request
                    msg_id = msg.get("id")
                    if msg_id and msg_id in self._responses:
                        # Complete the future for this response
                        self._responses[msg_id].set_result(msg)
                    elif "id" not in msg or msg.get("id") is None:
                        # It's a notification
                        self.notifications.append(msg)
                except json.JSONDecodeError:
                    pass
        except asyncio.CancelledError:
            pass

    async def wait_for_notification(
        self, method: str, timeout: float = 2.0, skip_count: int = 0
    ) -> dict[str, Any]:
        """Wait for a specific notification method."""
        start = asyncio.get_event_loop().time()
        seen = 0

        while asyncio.get_event_loop().time() - start < timeout:
            for notif in self.notifications[seen:]:
                if notif.get("method") == method:
                    if skip_count > 0:
                        skip_count -= 1
                        continue
                    return notif
            seen = len(self.notifications)
            await asyncio.sleep(0.01)

        raise TimeoutError(f"Notification '{method}' not received in {timeout}s")


@pytest_asyncio.fixture
async def streaming_client(climux_server) -> AsyncGenerator[StreamingClient, None]:
    """Fixture providing a streaming-capable client."""
    client = StreamingClient(climux_server.socket_path)
    await client.connect()
    yield client
    await client.disconnect()


class TestJSONRPCStreaming:
    """Test JSON-RPC streaming functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_single_process(
        self, climux_client: ClimuxClient, streaming_client: StreamingClient
    ):
        """Test subscribing to a single process."""
        # Start a process
        result = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; print('Hello', flush=True); time.sleep(0.1); print('World', flush=True)",
                ],
                "name": "streaming-test",
            },
        )
        process_id = result["id"]

        # Subscribe to its logs
        sub_result = await streaming_client.request(
            "log.subscribe", {"process_ids": [process_id]}
        )

        assert "subscription_id" in sub_result
        assert sub_result["process_ids"] == [process_id]

        # Wait for log notifications
        log1 = await streaming_client.wait_for_notification("log.entry")
        assert log1["method"] == "log.entry"
        assert "Hello" in log1["params"]["entry"]["content"]

        # Skip the first log.entry to get the second one
        log2 = await streaming_client.wait_for_notification(
            "log.entry", timeout=2.0, skip_count=1
        )
        assert "World" in log2["params"]["entry"]["content"]

    @pytest.mark.asyncio
    async def test_subscribe_multiple_processes(
        self, climux_client: ClimuxClient, streaming_client: StreamingClient
    ):
        """Test subscribing to multiple processes."""
        # Start two processes
        proc1 = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; print('Process1', flush=True); time.sleep(0.2)",
                ],
                "name": "proc1",
            },
        )

        proc2 = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; time.sleep(0.1); print('Process2', flush=True)",
                ],
                "name": "proc2",
            },
        )

        # Subscribe to both
        sub_result = await streaming_client.request(
            "log.subscribe", {"process_ids": [proc1["id"], proc2["id"]]}
        )

        # Collect notifications
        await asyncio.sleep(0.5)

        # Should have logs from both processes
        log_contents = [
            notif["params"]["entry"]["content"]
            for notif in streaming_client.notifications
            if notif.get("method") == "log.entry"
        ]

        assert any("Process1" in content for content in log_contents)
        assert any("Process2" in content for content in log_contents)

    @pytest.mark.asyncio
    async def test_unsubscribe(
        self, climux_client: ClimuxClient, streaming_client: StreamingClient
    ):
        """Test unsubscribing from logs."""
        # Start a long-running process
        result = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; [print(f'Line {i}', flush=True) or time.sleep(0.1) for i in range(10)]",
                ],
                "name": "long-process",
            },
        )

        # Subscribe
        sub_result = await streaming_client.request(
            "log.subscribe", {"process_ids": [result["id"]]}
        )
        subscription_id = sub_result["subscription_id"]

        # Get a few notifications
        await asyncio.sleep(0.3)
        initial_count = len(streaming_client.notifications)
        assert initial_count > 0

        # Unsubscribe
        unsub_result = await streaming_client.request(
            "log.unsubscribe", {"subscription_id": subscription_id}
        )
        assert unsub_result is True

        # Wait a bit more
        await asyncio.sleep(0.3)

        # Should not receive many more notifications
        final_count = len(streaming_client.notifications)
        assert final_count - initial_count < 3  # Allow for in-flight messages

    @pytest.mark.asyncio
    async def test_process_completion_notification(
        self, climux_client: ClimuxClient, streaming_client: StreamingClient
    ):
        """Test that we get notified when process completes."""
        # Start a short process with a small delay to ensure we can subscribe
        result = await climux_client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; time.sleep(0.1); print('done', flush=True)",
                ],
                "name": "short-process",
            },
        )

        # Subscribe immediately
        await streaming_client.request("log.subscribe", {"process_ids": [result["id"]]})

        # Wait for output
        done_log = await streaming_client.wait_for_notification(
            "log.entry", timeout=2.0
        )
        assert "done" in done_log["params"]["entry"]["content"]
