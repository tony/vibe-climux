# CLAUDE.local.md

This file tracks local development context and strategic goals for the climux project.

## Current Work: Implicit Server Start (tmux-like behavior)

### Strategic Goal
Transform climux from a traditional client-server model (where users must explicitly start the server) to a tmux-like experience where the server starts automatically when needed. This makes climux feel more intuitive and reduces friction for both human developers and AI agents.

### Project Goal  
Create a headless CLI process manager that works seamlessly for both local development and agentic workflows. The key insight is that users shouldn't have to think about the server - it should just work.

### What We're Doing Now (2025-08-04)

#### Problem
Currently, climux requires explicit server management:
```bash
# Current (cumbersome) workflow:
climux server &  # Step 1: Start server
climux start npm run dev  # Step 2: Use it

# Desired (tmux-like) workflow:
climux start npm run dev  # Server starts automatically if needed
```

#### Approach
1. **Test-First Development**: We've built a comprehensive test harness that can control server lifecycle precisely
   - `managed_server` fixture for fine-grained async control
   - `server_controller` fixture for subprocess-based testing (real CLI behavior)
   - `cli_runner` fixture for simulating user interactions
   - Tests in `test_server_lifecycle.py` that define the desired behavior

2. **Implementation Plan**:
   - Client checks if server is running (socket exists and responsive)
   - If no server, fork one in background before executing command
   - Server command should daemonize properly (return immediately)
   - Fix bug on line 676 of climux.py (using wrong args attribute)

3. **Key Technical Decisions**:
   - Server persists after client exits (like tmux)
   - Use default socket unless -L or -S specified
   - Clean up stale sockets/PIDs on server start
   - No auto-shutdown when last process exits (for now)

#### Test Status
- ✅ Enhanced test fixtures for server lifecycle control
- ✅ Socket state verification utilities  
- ✅ Tests for implicit server start behavior (all passing!)
- ✅ Implemented implicit server start in climux.py
- ⏳ Server attachment/detachment tests (future feature)

#### Implementation Complete! 🎉

Successfully implemented tmux-like implicit server start:

1. **Fixed the bug**: Changed `args.command` to `args.subcommand` (argparse naming collision)
2. **Added server checks**: `is_server_running()` function that verifies socket exists and server responds to ping
3. **Automatic spawning**: `start_server_daemon()` uses double-fork pattern for proper daemonization
4. **Client integration**: All client commands now check for server and start it if needed
5. **All tests passing**: Both server lifecycle tests and main test suite are green

The implementation provides:
- Server starts automatically on first client command
- Server persists after client exits
- Multiple servers supported via -L and -S options
- Proper cleanup of stale sockets and PIDs
- Graceful handling of socket conflicts

#### What Changed
1. **climux.py**:
   - Added `is_server_running(socket_path)` - checks if server is alive
   - Added `start_server_daemon(socket_path)` - double-fork daemonization
   - Modified `main()` to auto-start server for client commands
   - Server command now checks if already running

2. **Behavior**:
   - `climux start npm run dev` now just works (no manual server start)
   - `climux server` detects if already running and exits gracefully
   - Server runs as proper daemon (detached from terminal)

### Original Task Context
User wanted to set up a file watcher with `entr` and `uv run mypy`, which revealed that the current climux UX requires manual server management. This led to the realization that climux should behave more like tmux with implicit server instantiation.

### Design Principles
- **Delicate State Handling**: Server lifecycle is complex and needs thorough testing
- **User Experience First**: The tool should feel natural and effortless
- **Test Everything**: Use pytest fixtures to control and verify all state transitions
- **Learn from tmux**: Study how tmux makes client-server architecture invisible

## UX Improvements Proposal (2025-08-04)

Based on analysis of the current CLI, here are proposed improvements to make climux more user-friendly.

### 1. Real-Time Log Tailing

#### Current Issues
- `tail` command doesn't actually tail - just shows recent logs
- No way to follow logs in real-time
- Must repeatedly run `logs` command to see new output

#### Proposed Solution
```bash
# Follow logs from a specific process
climux logs --tail <process>
climux logs -f <process>  # Short flag

# Follow logs from ALL processes (multiplexed)
climux logs --tail --all
climux logs -f -a
```

#### Implementation
- Use existing `tail_logs()` queue infrastructure in `ManagedProcess`
- Add WebSocket or streaming support to JSON-RPC protocol
- For CLI, poll with deduplication until proper streaming is implemented

### 2. Process Name Support

#### Current Issues
- Must use numeric IDs: `climux stop 5`
- Hard to remember which ID maps to which process
- Error-prone when working with multiple processes

#### Proposed Solution
```bash
# Support process names everywhere
climux stop myapp
climux restart frontend
climux logs backend
climux send test-runner "q\n"

# Resolution rules:
# 1. Try as numeric ID first
# 2. Look for running process with that name
# 3. Fall back to any process with that name
```

### 3. Command Aliases

#### Current Issues
- Commands are verbose for common operations
- Not aligned with familiar Unix conventions

#### Proposed Solution
```bash
# Add familiar aliases
climux ls     # alias for 'list'
climux ps     # alias for 'list' (like Unix ps)

# Future possibilities:
climux rm     # alias for 'stop'
climux exec   # alias for 'send'
```

### 4. Improved List Output

#### Current Issues
- Output format could be cleaner
- No JSON output for scripting
- Uptime strings can be very long

#### Proposed Solution
```bash
# Clean table format (default)
$ climux list
ID     Name                 Status     PID        Uptime         
-----------------------------------------------------------------
1      frontend             running    12345      0:45:32        
2      backend              running    12346      0:45:30        
3      worker               exited     N/A        N/A            

# JSON output for scripting
$ climux list --json
[
  {
    "id": 1,
    "name": "frontend",
    "status": "running",
    "pid": 12345,
    ...
  }
]
```

### 5. Global Operations

#### Current Issues
- Can't see logs from all processes at once
- No way to monitor system-wide activity

#### Proposed Solution
```bash
# Show logs from all processes
climux logs --all
climux logs -a

# Tail all processes (with prefixes)
climux logs --tail --all
[frontend] 2024-01-15 10:30:45 [stdout] Server started on port 3000
[backend]  2024-01-15 10:30:46 [stdout] API listening on :8080
[worker]   2024-01-15 10:30:47 [stdout] Processing job #1234
```

### 6. Simplify Commands

#### Current Issues
- `tail` vs `logs` confusion
- `snapshot` command unclear purpose
- Too many ways to view logs

#### Proposed Solution
- Remove `tail` command (replace with `logs --tail`)
- Remove or clarify `snapshot` (maybe rename to `last` or integrate into `logs`)
- Consolidate log viewing into single `logs` command with flags

### 7. Better Error Messages

#### Current Issues
- "Process 5 not found" - not helpful if using names
- Generic "Failed to start process" without details

#### Proposed Solution
```bash
# More helpful error messages
$ climux stop frontend
Error: No process named 'frontend' found

$ climux stop 99
Error: No process with ID 99 found

$ climux start invalid-command
Error: Failed to start process: Command 'invalid-command' not found
```

### Implementation Priority

1. **High Priority** (Easy wins)
   - Process name support
   - Command aliases (ls, ps)
   - Improved list output format
   - Better error messages

2. **Medium Priority** (More complex)
   - Real-time log tailing for single process
   - Logs --all flag
   - JSON output option

3. **Low Priority** (Requires significant changes)
   - Global real-time tailing
   - WebSocket/streaming support
   - Command consolidation

### Backward Compatibility

All changes should be backward compatible:
- Numeric IDs continue to work
- Existing commands remain available
- New features are additions, not replacements

### Example Usage After Improvements

```bash
# Start processes with meaningful names
climux start npm run dev --name frontend
climux start python api.py --name backend
climux start python worker.py --name worker

# Use names instead of IDs
climux ps                    # See clean list
climux logs backend -n 50    # Last 50 lines
climux logs frontend -f      # Follow frontend logs
climux logs -a               # See all logs
climux restart backend       # Restart by name
climux stop worker           # Stop by name

# JSON output for scripting
climux ps --json | jq '.[] | select(.status=="running") | .name'
```

These improvements would make climux more intuitive for both human users and AI agents, reducing cognitive load and making common operations faster.

## Real-Time Log Testing Questions (2025-08-04)

### Context
Working on implementing real-time log tailing for climux. Created test fixtures in `test_realtime_logs.py` but encountering challenges with asyncio, pytest, and streaming architecture.

### Questions for Expert Research

#### 1. Real-time Log Streaming Architecture
- How to extend JSON-RPC over Unix sockets for streaming (no WebSockets/SSE)?
- Best pattern for handling backpressure with 10-100 msgs/sec normal, 1000+ bursts?
- How to multiplex logs from 5-50+ processes into single stream?

#### 2. Testing Asyncio Queue-based Streaming
- Is the LogStreamCollector pattern with `asyncio.wait_for(queue.get(), timeout=0.1)` correct?
- How to ensure no logs missed between process start and monitor attachment?
- Best practices for background task cleanup in test fixtures?

#### 3. Pytest-asyncio Integration
- How to synchronize test assertions with async log generation?
- `asyncio.gather()` vs `asyncio.create_task()` for multiple monitors?
- Best timeout patterns - `asyncio.wait_for()` vs pytest timeouts?

#### 4. Process Output Buffering Issues
- Short-lived processes (`echo "text"`) exit before output captured
- Python with `flush=True` works, but simple commands don't
- How to ensure all output captured before process exit in async context?

#### 5. Testing High-Volume Scenarios
- Pattern for verifying no logs dropped under high volume?
- How to verify ordering preserved with multiple concurrent processes?
- Should assertions be in collector or after collection?

#### 6. JSON-RPC Streaming Extensions
- Best way to implement subscribe/unsubscribe for tailing over JSON-RPC?
- Should use separate endpoint or extend existing protocol?
- How to handle client disconnection during streaming?

#### 7. Test Fixture Design
- Is the current fixture pattern (setup collectors/tasks, yield function, cleanup) correct?
- How to handle cleanup when tests fail?
- Should fixtures manage own event loop or rely on pytest-asyncio's?

#### 8. Race Condition Prevention
- Process starting/exiting before monitor attaches
- Logs added between queue creation and collection start
- Test assertions running before async operations complete
- What patterns prevent these races?

### Requirements & Constraints
- **Must use**: Unix sockets + JSON-RPC (no external deps)
- **Python**: 3.13+ standard library only
- **Performance**: 10-100 msgs/sec normal, handle 1000+ bursts
- **Scale**: 5-20 processes typical, support 50+
- **Testing**: pytest-xdist compatible, <5 sec per test, no flaky failures
- **Environment**: Local + GitHub Actions CI (2 cores, 7GB RAM)