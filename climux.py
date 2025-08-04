#!/usr/bin/env python3
"""
climux: A headless CLI process manager with JSON-RPC control.

A tmux-like process manager for headless/agentic workflows, using only
Python 3.13+ standard library. Manages background processes with full
programmatic control via JSON-RPC 2.0 over Unix sockets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

# --- Constants ---
SOCKET_DIR = Path(tempfile.gettempdir()) / "climux"
DEFAULT_SOCKET_NAME = "default.sock"
PID_JOURNAL_PREFIX = "climux_pids_"
DEFAULT_MAX_LOG_LINES = 1000
DEFAULT_MAX_LOG_HOURS = 24
SNAPSHOT_DEFAULT_LINES = 25


# --- Data Structures ---
@dataclass
class ProcessConfig:
    """Configuration for a managed process."""

    command: List[str]
    name: Optional[str] = None
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    max_log_lines: int = DEFAULT_MAX_LOG_LINES
    max_log_hours: float = DEFAULT_MAX_LOG_HOURS


@dataclass
class LogEntry:
    """A single log entry with timestamp and content."""

    timestamp: datetime
    source: str  # stdout, stderr, or system
    content: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "content": self.content,
        }


@dataclass
class ManagedProcess:
    """A process managed by climux."""

    id: int
    config: ProcessConfig
    process: Optional[asyncio.subprocess.Process] = None
    status: str = "stopped"  # stopped, running, failed, exited
    pid: Optional[int] = None
    exit_code: Optional[int] = None
    start_time: Optional[datetime] = None
    logs: Deque[LogEntry] = field(default_factory=deque)
    _log_watchers: List[asyncio.Queue[Optional[LogEntry]]] = field(
        default_factory=list
    )

    async def start(self) -> bool:
        """Start the process."""
        if self.status == "running":
            return False

        try:
            # Prepare environment
            env = os.environ.copy()
            if self.config.env:
                env.update(self.config.env)

            # Start process
            self.process = await asyncio.create_subprocess_exec(
                *self.config.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
                env=env,
                start_new_session=True,  # Create new process group
            )

            self.pid = self.process.pid
            self.status = "running"
            self.start_time = datetime.now(timezone.utc)
            self.exit_code = None

            # Start log handlers
            asyncio.create_task(self._read_stream(self.process.stdout, "stdout"))
            asyncio.create_task(self._read_stream(self.process.stderr, "stderr"))
            asyncio.create_task(self._monitor_exit())

            self._add_log(
                "system", f"Process started with PID {self.pid}"
            )
            return True

        except Exception as e:
            self.status = "failed"
            self._add_log("system", f"Failed to start: {e}")
            return False

    async def stop(self) -> bool:
        """Stop the process gracefully."""
        if not self.process or self.status != "running":
            return False

        try:
            self._add_log("system", f"Sending SIGTERM to PID {self.pid}")
            self.process.terminate()
            await asyncio.wait_for(self.process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            self._add_log("system", f"Process did not terminate, sending SIGKILL")
            self.process.kill()
            await self.process.wait()

        return True

    async def restart(self) -> bool:
        """Restart the process."""
        await self.stop()
        await asyncio.sleep(0.1)  # Brief pause before restart
        return await self.start()

    async def send_input(self, data: str) -> bool:
        """Send input to the process's stdin."""
        if not self.process or not self.process.stdin or self.status != "running":
            return False

        try:
            if not data.endswith("\n"):
                data += "\n"
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()
            self._add_log("stdin", data.rstrip())
            return True
        except (BrokenPipeError, ConnectionResetError) as e:
            self._add_log("system", f"Failed to write to stdin: {e}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get current status as a dictionary."""
        uptime = None
        if self.start_time and self.status == "running":
            uptime = str(datetime.now(timezone.utc) - self.start_time)

        return {
            "id": self.id,
            "name": self.config.name or f"process-{self.id}",
            "command": " ".join(self.config.command),
            "status": self.status,
            "pid": self.pid,
            "exit_code": self.exit_code,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime": uptime,
        }

    def get_logs(
        self, lines: Optional[int] = None, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get logs, optionally filtered."""
        logs = list(self.logs)

        # Filter by time
        if since:
            logs = [log for log in logs if log.timestamp >= since]

        # Trim old logs by age
        if self.config.max_log_hours > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=self.config.max_log_hours
            )
            logs = [log for log in logs if log.timestamp >= cutoff]

        # Limit number of lines
        if lines:
            logs = logs[-lines:]

        return [log.to_dict() for log in logs]

    async def tail_logs(self) -> asyncio.Queue[Optional[LogEntry]]:
        """Create a queue for tailing logs in real-time."""
        queue: asyncio.Queue[Optional[LogEntry]] = asyncio.Queue()
        self._log_watchers.append(queue)
        return queue

    def stop_tail(self, queue: asyncio.Queue[Optional[LogEntry]]) -> None:
        """Stop tailing logs."""
        if queue in self._log_watchers:
            self._log_watchers.remove(queue)

    # --- Private methods ---

    def _add_log(self, source: str, content: str) -> None:
        """Add a log entry and notify watchers."""
        entry = LogEntry(
            timestamp=datetime.now(timezone.utc),
            source=source,
            content=content,
        )

        # Add to buffer with size limit
        self.logs.append(entry)
        if self.config.max_log_lines > 0:
            while len(self.logs) > self.config.max_log_lines:
                self.logs.popleft()

        # Notify watchers
        for queue in self._log_watchers:
            try:
                queue.put_nowait(entry)
            except asyncio.QueueFull:
                pass

    async def _read_stream(
        self, stream: Optional[asyncio.StreamReader], source: str
    ) -> None:
        """Read from a stream and log the output."""
        if not stream:
            return

        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                content = line.decode(errors="replace").rstrip()
                if content:  # Skip empty lines
                    self._add_log(source, content)
        except Exception as e:
            self._add_log("system", f"Error reading {source}: {e}")

    async def _monitor_exit(self) -> None:
        """Monitor process exit and update status."""
        if not self.process:
            return

        self.exit_code = await self.process.wait()
        self.status = "exited"
        self.pid = None
        self._add_log("system", f"Process exited with code {self.exit_code}")

        # Notify watchers that stream ended
        for queue in self._log_watchers:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                pass
        self._log_watchers.clear()


# --- Server ---
class ClimuxServer:
    """The climux server that manages processes."""

    def __init__(self, socket_path: Path):
        self.socket_path = socket_path
        self.pid_journal_path = socket_path.parent / (
            PID_JOURNAL_PREFIX + socket_path.stem + ".json"
        )
        self.processes: Dict[int, ManagedProcess] = {}
        self.next_id = 1
        self._server: Optional[asyncio.Server] = None
        self._running = False

    async def start(self) -> None:
        """Start the server."""
        # Ensure socket directory exists
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)

        # Clean up stale PIDs from previous runs
        await self._cleanup_stale_pids()

        # Remove old socket if it exists
        if self.socket_path.exists():
            self.socket_path.unlink()

        # Start server
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.socket_path)
        )
        self._running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))

        print(f"Climux server listening on {self.socket_path}")

        async with self._server:
            await self._server.serve_forever()

    async def shutdown(self) -> None:
        """Shut down the server and all processes."""
        if not self._running:
            return

        print("\nShutting down climux server...")
        self._running = False

        # Stop all processes
        tasks = []
        for process in self.processes.values():
            if process.status == "running":
                tasks.append(process.stop())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Clean up files
        self.socket_path.unlink(missing_ok=True)
        self.pid_journal_path.unlink(missing_ok=True)

        print("Climux server stopped.")

    # --- Client handling ---

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection."""
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break

                try:
                    request = json.loads(data.decode())
                    response = await self._dispatch_request(request)
                except json.JSONDecodeError as e:
                    response = self._error_response(
                        -32700, f"Parse error: {e}", None
                    )
                except Exception as e:
                    response = self._error_response(
                        -32603, f"Internal error: {e}", None
                    )

                writer.write(json.dumps(response).encode() + b"\n")
                await writer.drain()

        except asyncio.CancelledError:
            raise
        except Exception:
            pass  # Client disconnected
        finally:
            writer.close()
            await writer.wait_closed()

    async def _dispatch_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        req_id = request.get("id")

        handlers = {
            "start": self._handle_start,
            "list": self._handle_list,
            "stop": self._handle_stop,
            "restart": self._handle_restart,
            "send": self._handle_send,
            "logs": self._handle_logs,
            "tail": self._handle_tail,
            "snapshot": self._handle_snapshot,
            "ping": self._handle_ping,
        }

        handler = handlers.get(method)
        if not handler:
            return self._error_response(-32601, f"Method not found: {method}", req_id)

        try:
            result = await handler(params)
            return {"jsonrpc": "2.0", "result": result, "id": req_id}
        except Exception as e:
            return self._error_response(-32000, str(e), req_id)

    # --- Request handlers ---

    async def _handle_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start a new process."""
        command = params.get("command", [])
        if not command:
            raise ValueError("Command is required")

        config = ProcessConfig(
            command=command,
            name=params.get("name"),
            cwd=Path(params["cwd"]) if "cwd" in params else None,
            env=params.get("env"),
            max_log_lines=params.get("max_log_lines", DEFAULT_MAX_LOG_LINES),
            max_log_hours=params.get("max_log_hours", DEFAULT_MAX_LOG_HOURS),
        )

        process_id = self.next_id
        self.next_id += 1

        process = ManagedProcess(id=process_id, config=config)
        self.processes[process_id] = process

        success = await process.start()
        if success:
            self._update_pid_journal()
            return process.get_status()
        else:
            del self.processes[process_id]
            raise RuntimeError("Failed to start process")

    async def _handle_list(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List all processes."""
        return [p.get_status() for p in self.processes.values()]

    async def _handle_stop(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Stop a process."""
        process_id = params.get("id")
        process = self.processes.get(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        await process.stop()
        self._update_pid_journal()
        return {"status": "stopped", "id": process_id}

    async def _handle_restart(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Restart a process."""
        process_id = params.get("id")
        process = self.processes.get(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        await process.restart()
        self._update_pid_journal()
        return process.get_status()

    async def _handle_send(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Send input to a process."""
        process_id = params.get("id")
        data = params.get("data", "")

        process = self.processes.get(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        success = await process.send_input(data)
        if not success:
            raise RuntimeError("Failed to send input")

        return {"status": "sent", "id": process_id}

    async def _handle_logs(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get process logs."""
        process_id = params.get("id")
        lines = params.get("lines")

        process = self.processes.get(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        return process.get_logs(lines=lines)

    async def _handle_tail(self, params: Dict[str, Any]) -> Dict[str, str]:
        """Tail process logs (streaming not implemented in basic version)."""
        # For simplicity, return recent logs
        return await self._handle_logs(params)

    async def _handle_snapshot(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get a snapshot of recent output."""
        process_id = params.get("id")
        lines = params.get("lines", SNAPSHOT_DEFAULT_LINES)

        process = self.processes.get(process_id)
        if not process:
            raise ValueError(f"Process {process_id} not found")

        return process.get_logs(lines=lines)

    async def _handle_ping(self, params: Dict[str, Any]) -> str:
        """Ping the server."""
        return "pong"

    # --- Helper methods ---

    def _error_response(
        self, code: int, message: str, req_id: Optional[Any]
    ) -> Dict[str, Any]:
        """Create a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": req_id,
        }

    def _update_pid_journal(self) -> None:
        """Update the PID journal file."""
        pids = {}
        for process in self.processes.values():
            if process.pid:
                pids[str(process.id)] = process.pid

        try:
            self.pid_journal_path.write_text(json.dumps(pids))
        except Exception:
            pass  # Best effort

    async def _cleanup_stale_pids(self) -> None:
        """Clean up PIDs from a previous run."""
        if not self.pid_journal_path.exists():
            return

        try:
            pids = json.loads(self.pid_journal_path.read_text())
            for process_id, pid in pids.items():
                try:
                    os.kill(pid, signal.SIGKILL)
                    print(f"Killed stale process {process_id} (PID {pid})")
                except ProcessLookupError:
                    pass  # Already dead
        except Exception:
            pass  # Ignore errors
        finally:
            self.pid_journal_path.unlink(missing_ok=True)


# --- Client ---
class ClimuxClient:
    """Client for interacting with the climux server."""

    def __init__(self, socket_path: Path):
        self.socket_path = socket_path

    async def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Send a request to the server."""
        try:
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
        except (FileNotFoundError, ConnectionRefusedError):
            raise RuntimeError(f"Cannot connect to server at {self.socket_path}")

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }

        writer.write(json.dumps(request).encode() + b"\n")
        await writer.drain()

        response_data = await reader.readline()
        writer.close()
        await writer.wait_closed()

        if not response_data:
            raise RuntimeError("Empty response from server")

        response = json.loads(response_data.decode())
        if "error" in response:
            raise RuntimeError(f"Server error: {response['error']['message']}")

        return response.get("result")


# --- CLI ---
def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Climux: A headless CLI process manager"
    )
    parser.add_argument(
        "-L",
        "--socket-name",
        default=DEFAULT_SOCKET_NAME,
        help="Socket name in temp directory",
    )
    parser.add_argument(
        "-S",
        "--socket-path",
        type=Path,
        help="Full path to socket",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Server command
    subparsers.add_parser("server", help="Start the climux server")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new process")
    start_parser.add_argument("command", nargs="+", help="Command to run")
    start_parser.add_argument("--name", help="Process name")
    start_parser.add_argument("--cwd", type=Path, help="Working directory")
    start_parser.add_argument(
        "--max-lines",
        type=int,
        default=DEFAULT_MAX_LOG_LINES,
        help="Max log lines to keep",
    )
    start_parser.add_argument(
        "--max-hours",
        type=float,
        default=DEFAULT_MAX_LOG_HOURS,
        help="Max log age in hours",
    )

    # Other commands
    subparsers.add_parser("list", help="List all processes")

    stop_parser = subparsers.add_parser("stop", help="Stop a process")
    stop_parser.add_argument("id", type=int, help="Process ID")

    restart_parser = subparsers.add_parser("restart", help="Restart a process")
    restart_parser.add_argument("id", type=int, help="Process ID")

    send_parser = subparsers.add_parser("send", help="Send input to a process")
    send_parser.add_argument("id", type=int, help="Process ID")
    send_parser.add_argument("data", help="Data to send")

    logs_parser = subparsers.add_parser("logs", help="Show process logs")
    logs_parser.add_argument("id", type=int, help="Process ID")
    logs_parser.add_argument(
        "--lines", type=int, help="Number of lines to show"
    )

    tail_parser = subparsers.add_parser("tail", help="Tail process logs")
    tail_parser.add_argument("id", type=int, help="Process ID")

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Get snapshot of recent output"
    )
    snapshot_parser.add_argument("id", type=int, help="Process ID")
    snapshot_parser.add_argument(
        "--lines",
        type=int,
        default=SNAPSHOT_DEFAULT_LINES,
        help="Number of lines",
    )

    subparsers.add_parser("ping", help="Ping the server")

    args = parser.parse_args()

    # Determine socket path
    if args.socket_path:
        socket_path = args.socket_path
    else:
        SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        socket_path = SOCKET_DIR / args.socket_name

    # Handle commands
    if args.command == "server":
        server = ClimuxServer(socket_path)
        asyncio.run(server.start())

    else:
        # Client commands
        client = ClimuxClient(socket_path)

        async def run_client():
            if args.command == "start":
                params = {
                    "command": args.command,
                    "name": args.name,
                    "max_log_lines": args.max_lines,
                    "max_log_hours": args.max_hours,
                }
                if args.cwd:
                    params["cwd"] = str(args.cwd)
                result = await client.request("start", params)
                print(f"Started process {result['id']}: {result['name']}")

            elif args.command == "list":
                result = await client.request("list")
                if not result:
                    print("No processes running")
                else:
                    for proc in result:
                        print(
                            f"[{proc['id']}] {proc['name']}: {proc['status']} "
                            f"(PID: {proc['pid'] or 'N/A'})"
                        )

            elif args.command == "stop":
                result = await client.request("stop", {"id": args.id})
                print(f"Stopped process {result['id']}")

            elif args.command == "restart":
                result = await client.request("restart", {"id": args.id})
                print(f"Restarted process {result['id']}: {result['name']}")

            elif args.command == "send":
                result = await client.request(
                    "send", {"id": args.id, "data": args.data}
                )
                print(f"Sent input to process {result['id']}")

            elif args.command == "logs":
                params = {"id": args.id}
                if args.lines:
                    params["lines"] = args.lines
                result = await client.request("logs", params)
                for entry in result:
                    print(
                        f"[{entry['timestamp']}] [{entry['source']}] {entry['content']}"
                    )

            elif args.command == "tail":
                result = await client.request("tail", {"id": args.id})
                for entry in result:
                    print(
                        f"[{entry['timestamp']}] [{entry['source']}] {entry['content']}"
                    )

            elif args.command == "snapshot":
                result = await client.request(
                    "snapshot", {"id": args.id, "lines": args.lines}
                )
                for entry in result:
                    print(entry["content"])

            elif args.command == "ping":
                result = await client.request("ping")
                print(result)

        try:
            asyncio.run(run_client())
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()