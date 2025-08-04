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
- ✅ Tests for implicit server start behavior (failing as expected)
- 🚧 Implement implicit server start in climux.py
- ⏳ Server attachment/detachment tests (future feature)

#### Next Steps
1. Fix the bug in client command handling (line 676)
2. Add server existence check in client
3. Implement automatic server spawning
4. Make server command daemonize properly
5. Verify all tests pass

### Original Task Context
User wanted to set up a file watcher with `entr` and `uv run mypy`, which revealed that the current climux UX requires manual server management. This led to the realization that climux should behave more like tmux with implicit server instantiation.

### Design Principles
- **Delicate State Handling**: Server lifecycle is complex and needs thorough testing
- **User Experience First**: The tool should feel natural and effortless
- **Test Everything**: Use pytest fixtures to control and verify all state transitions
- **Learn from tmux**: Study how tmux makes client-server architecture invisible