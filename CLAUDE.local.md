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