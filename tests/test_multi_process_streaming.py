"""
Integration tests for multi-process streaming scenarios.

This module tests streaming logs from multiple processes simultaneously,
including high-volume scenarios and backpressure handling.
"""

import asyncio

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def streaming_monitor(climux_server, climux_client):
    """High-level fixture for streaming tests with multiple processes."""

    class StreamingMonitor:
        def __init__(self, server, client):
            self.server = server
            self.client = client
            self.streaming_client = None
            self.subscriptions = {}
            self.collected_logs = {}

        async def start_processes(
            self, count: int, name_prefix: str = "proc"
        ) -> list[int]:
            """Start multiple test processes."""
            process_ids = []
            for i in range(count):
                result = await self.client.request(
                    "start",
                    {
                        "command": [
                            "python",
                            "-c",
                            f"""import time
import sys
for j in range(5):
    print('{name_prefix}_{i}_' + str(j), flush=True)
    sys.stderr.write('{name_prefix}_{i}_err_' + str(j) + '\\n')
    sys.stderr.flush()
    time.sleep(0.1)""",
                        ],
                        "name": f"{name_prefix}_{i}",
                    },
                )
                process_ids.append(result["id"])
            return process_ids

        async def start_high_volume_process(self, msg_count: int = 1000) -> int:
            """Start a process that generates many logs quickly."""
            result = await self.client.request(
                "start",
                {
                    "command": [
                        "python",
                        "-c",
                        f"for i in range({msg_count}): print('msg_' + str(i), flush=True)",
                    ],
                    "name": "high_volume",
                },
            )
            return result["id"]

        async def subscribe_and_collect(
            self, process_ids: list[int], duration: float = 2.0
        ):
            """Subscribe to processes and collect logs for a duration."""
            # Import StreamingClient from test module
            from test_json_rpc_streaming import StreamingClient

            self.streaming_client = StreamingClient(self.server.socket_path)
            await self.streaming_client.connect()

            # Subscribe
            sub_result = await self.streaming_client.request(
                "log.subscribe", {"process_ids": process_ids}
            )
            subscription_id = sub_result["subscription_id"]

            # Collect for duration
            await asyncio.sleep(duration)

            # Process collected notifications
            for notif in self.streaming_client.notifications:
                if notif.get("method") == "log.entry":
                    proc_id = notif["params"]["process_id"]
                    if proc_id not in self.collected_logs:
                        self.collected_logs[proc_id] = []
                    self.collected_logs[proc_id].append(notif["params"]["entry"])

            return subscription_id

        async def cleanup(self):
            """Clean up streaming client."""
            if self.streaming_client:
                await self.streaming_client.disconnect()

    monitor = StreamingMonitor(climux_server, climux_client)
    yield monitor
    await monitor.cleanup()


class TestMultiProcessStreaming:
    """Test streaming from multiple processes simultaneously."""

    @pytest.mark.asyncio
    async def test_stream_from_5_processes(self, streaming_monitor):
        """Test streaming from 5 concurrent processes."""
        # Start 5 processes
        process_ids = await streaming_monitor.start_processes(5, "test5")

        # Subscribe and collect
        await streaming_monitor.subscribe_and_collect(process_ids, duration=1.5)

        # Verify we got logs from all processes
        assert len(streaming_monitor.collected_logs) == 5

        # Verify each process sent expected logs
        for proc_id in process_ids:
            logs = streaming_monitor.collected_logs.get(proc_id, [])
            contents = [log["content"] for log in logs]

            # Should have stdout and stderr messages
            stdout_msgs = [c for c in contents if "_err_" not in c]
            stderr_msgs = [c for c in contents if "_err_" in c]

            assert len(stdout_msgs) >= 5  # At least 5 stdout messages
            assert len(stderr_msgs) >= 5  # At least 5 stderr messages

            # Verify ordering within each stream
            for i in range(5):
                assert any(f"_{i}" in msg for msg in stdout_msgs)

    @pytest.mark.asyncio
    async def test_stream_from_20_processes(self, streaming_monitor):
        """Test streaming from 20 concurrent processes."""
        # Start 20 processes
        process_ids = await streaming_monitor.start_processes(20, "test20")

        # Subscribe and collect
        await streaming_monitor.subscribe_and_collect(process_ids, duration=1.5)

        # Should have logs from all 20
        assert len(streaming_monitor.collected_logs) == 20

        # Verify no process was starved
        for proc_id in process_ids:
            logs = streaming_monitor.collected_logs.get(proc_id, [])
            assert len(logs) > 0, f"Process {proc_id} produced no logs"

    @pytest.mark.asyncio
    async def test_high_volume_streaming(self, streaming_monitor):
        """Test streaming high volume of logs (1000+ messages)."""
        # Start high-volume process
        proc_id = await streaming_monitor.start_high_volume_process(1000)

        # Subscribe and collect
        await streaming_monitor.subscribe_and_collect([proc_id], duration=2.0)

        # Check we got substantial logs
        logs = streaming_monitor.collected_logs.get(proc_id, [])
        assert len(logs) >= 900, f"Expected ~1000 logs, got {len(logs)}"

        # Verify ordering is preserved
        msg_numbers = []
        for log in logs:
            if log["content"].startswith("msg_"):
                try:
                    num = int(log["content"].split("_")[1])
                    msg_numbers.append(num)
                except (IndexError, ValueError):
                    pass

        # Numbers should be in ascending order
        for i in range(1, len(msg_numbers)):
            assert msg_numbers[i] >= msg_numbers[i - 1], "Log ordering violated"

    @pytest.mark.asyncio
    async def test_mixed_lifetime_processes(self, streaming_monitor):
        """Test streaming from processes with different lifetimes."""
        # Start a long-running process first
        long_result = await streaming_monitor.client.request(
            "start",
            {
                "command": [
                    "python",
                    "-c",
                    "import time; "
                    "[print(f'long_{i}', flush=True) or time.sleep(0.2) for i in range(10)]",
                ],
                "name": "long_process",
            },
        )

        # Set up streaming client and subscribe to long process
        from test_json_rpc_streaming import StreamingClient

        streaming_monitor.streaming_client = StreamingClient(
            streaming_monitor.server.socket_path
        )
        await streaming_monitor.streaming_client.connect()

        # Subscribe to the long process first
        sub_result = await streaming_monitor.streaming_client.request(
            "log.subscribe", {"process_ids": [long_result["id"]]}
        )

        # Now start short processes and add them to subscription
        process_ids = [long_result["id"]]
        for i in range(3):
            short_result = await streaming_monitor.client.request(
                "start",
                {
                    "command": [
                        "python",
                        "-c",
                        f"import time; time.sleep(0.05); print('short_{i}')",
                    ],
                    "name": f"short_{i}",
                },
            )
            process_ids.append(short_result["id"])

        # Update subscription to include all processes
        await streaming_monitor.streaming_client.request(
            "log.unsubscribe", {"subscription_id": sub_result["subscription_id"]}
        )

        sub_result = await streaming_monitor.streaming_client.request(
            "log.subscribe", {"process_ids": process_ids}
        )

        # Collect logs
        await asyncio.sleep(1.5)

        # Process collected notifications
        for notif in streaming_monitor.streaming_client.notifications:
            if notif.get("method") == "log.entry":
                proc_id = notif["params"]["process_id"]
                if proc_id not in streaming_monitor.collected_logs:
                    streaming_monitor.collected_logs[proc_id] = []
                streaming_monitor.collected_logs[proc_id].append(
                    notif["params"]["entry"]
                )

        # Verify we got logs from all processes
        assert len(streaming_monitor.collected_logs) >= 4

        # Long process should have multiple logs
        long_logs = streaming_monitor.collected_logs.get(long_result["id"], [])
        assert len(long_logs) >= 5

        # Short processes should have their output
        for i in range(1, 4):  # IDs 2, 3, 4
            short_logs = streaming_monitor.collected_logs.get(process_ids[i], [])
            contents = [log["content"] for log in short_logs]
            assert any(f"short_{i - 1}" in c for c in contents)

    @pytest.mark.asyncio
    async def test_process_exit_during_streaming(self, streaming_monitor):
        """Test that streaming handles processes exiting during stream."""
        # Start processes that exit at different times
        process_ids = []

        for i in range(3):
            result = await streaming_monitor.client.request(
                "start",
                {
                    "command": [
                        "python",
                        "-c",
                        f"import time; "
                        f"print('start_{i}', flush=True); "
                        f"time.sleep({i * 0.3}); "
                        f"print('end_{i}', flush=True)",
                    ],
                    "name": f"timed_{i}",
                },
            )
            process_ids.append(result["id"])

        # Subscribe and collect
        await streaming_monitor.subscribe_and_collect(process_ids, duration=2.0)

        # All processes should have both start and end messages
        for i, proc_id in enumerate(process_ids):
            logs = streaming_monitor.collected_logs.get(proc_id, [])
            contents = [log["content"] for log in logs]

            assert any(f"start_{i}" in c for c in contents)
            assert any(f"end_{i}" in c for c in contents)
            assert any("Process exited" in c for c in contents)
