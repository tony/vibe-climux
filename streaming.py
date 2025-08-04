"""
JSON-RPC streaming protocol extensions for real-time log tailing.

This module implements the server-side streaming functionality using
JSON-RPC 2.0 notifications over Unix sockets with LDJSON framing.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass

from climux import LogEntry, ManagedProcess


@dataclass
class Subscription:
    """Represents an active log subscription."""

    id: str
    process_ids: list[int]
    writer: asyncio.StreamWriter
    queue: asyncio.Queue[LogEntry | None]
    task: asyncio.Task[None] | None = None


class StreamingManager:
    """Manages log streaming subscriptions."""

    def __init__(self, processes: dict[int, ManagedProcess]):
        self.processes = processes
        self.subscriptions: dict[str, Subscription] = {}
        self._forwarder_tasks: dict[tuple[str, int], asyncio.Task] = {}

    async def subscribe(
        self, process_ids: list[int], writer: asyncio.StreamWriter
    ) -> str:
        """Create a new log subscription."""
        subscription_id = f"sub_{uuid.uuid4().hex[:8]}"

        # Create bounded queue for this subscription
        queue: asyncio.Queue[LogEntry | None] = asyncio.Queue(maxsize=1000)

        subscription = Subscription(
            id=subscription_id, process_ids=process_ids, writer=writer, queue=queue
        )

        self.subscriptions[subscription_id] = subscription

        # Start forwarder tasks for each process
        for process_id in process_ids:
            if process_id in self.processes:
                task = asyncio.create_task(
                    self._forward_logs(subscription_id, process_id)
                )
                self._forwarder_tasks[(subscription_id, process_id)] = task

        # Start streaming task
        subscription.task = asyncio.create_task(self._stream_logs(subscription_id))

        return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel a log subscription."""
        if subscription_id not in self.subscriptions:
            return False

        subscription = self.subscriptions[subscription_id]

        # Cancel forwarder tasks
        for process_id in subscription.process_ids:
            key = (subscription_id, process_id)
            if key in self._forwarder_tasks:
                task = self._forwarder_tasks[key]
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                del self._forwarder_tasks[key]

        # Signal streaming task to stop
        await subscription.queue.put(None)

        # Cancel streaming task
        if subscription.task and not subscription.task.done():
            subscription.task.cancel()
            await asyncio.gather(subscription.task, return_exceptions=True)

        del self.subscriptions[subscription_id]
        return True

    async def cleanup_writer(self, writer: asyncio.StreamWriter) -> None:
        """Clean up all subscriptions for a disconnected client."""
        # Find all subscriptions for this writer
        to_remove = [
            sub_id for sub_id, sub in self.subscriptions.items() if sub.writer == writer
        ]

        # Unsubscribe them all
        for sub_id in to_remove:
            await self.unsubscribe(sub_id)

    async def _forward_logs(self, subscription_id: str, process_id: int) -> None:
        """Forward logs from a process to a subscription queue."""
        if subscription_id not in self.subscriptions:
            return

        subscription = self.subscriptions[subscription_id]
        process = self.processes.get(process_id)

        if not process:
            return

        # Get a tail queue from the process
        process_queue = await process.tail_logs()

        try:
            while True:
                # Wait for log entry from process
                entry = await process_queue.get()

                if entry is None:  # Process ended
                    # Don't forward the None - let process completion handle it
                    break

                # Add process ID to entry for multiplexing
                entry.process_id = process_id  # type: ignore

                # Forward to subscription queue with backpressure
                try:
                    subscription.queue.put_nowait(entry)
                except asyncio.QueueFull:
                    # Apply backpressure - wait for space
                    await subscription.queue.put(entry)

        except asyncio.CancelledError:
            # Clean up when cancelled
            process.stop_tail(process_queue)
            raise
        finally:
            # Always clean up the tail
            process.stop_tail(process_queue)

    async def _stream_logs(self, subscription_id: str) -> None:
        """Stream logs to the client via JSON-RPC notifications."""
        if subscription_id not in self.subscriptions:
            return

        subscription = self.subscriptions[subscription_id]

        try:
            while True:
                # Get next log entry
                entry = await subscription.queue.get()

                if entry is None:  # Subscription ended
                    break

                # Create JSON-RPC notification
                notification = {
                    "jsonrpc": "2.0",
                    "method": "log.entry",
                    "params": {
                        "subscription_id": subscription_id,
                        "process_id": getattr(entry, "process_id", None),
                        "entry": entry.to_dict(),
                    },
                }

                # Send as LDJSON (newline-delimited)
                try:
                    subscription.writer.write(json.dumps(notification).encode() + b"\n")
                    await subscription.writer.drain()
                except (ConnectionResetError, BrokenPipeError):
                    # Client disconnected
                    break

        except asyncio.CancelledError:
            pass
        finally:
            # Send completion notification if still connected
            try:
                completion = {
                    "jsonrpc": "2.0",
                    "method": "log.complete",
                    "params": {"subscription_id": subscription_id},
                }
                subscription.writer.write(json.dumps(completion).encode() + b"\n")
                await subscription.writer.drain()
            except:
                pass  # Ignore errors on completion
