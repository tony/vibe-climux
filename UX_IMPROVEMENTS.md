# Climux UX Improvements Proposal

Based on analysis of the current CLI, here are proposed improvements to make climux more user-friendly.

## 1. Real-Time Log Tailing

### Current Issues
- `tail` command doesn't actually tail - just shows recent logs
- No way to follow logs in real-time
- Must repeatedly run `logs` command to see new output

### Proposed Solution
```bash
# Follow logs from a specific process
climux logs --tail <process>
climux logs -f <process>  # Short flag

# Follow logs from ALL processes (multiplexed)
climux logs --tail --all
climux logs -f -a
```

### Implementation
- Use existing `tail_logs()` queue infrastructure in `ManagedProcess`
- Add WebSocket or streaming support to JSON-RPC protocol
- For CLI, poll with deduplication until proper streaming is implemented

## 2. Process Name Support

### Current Issues
- Must use numeric IDs: `climux stop 5`
- Hard to remember which ID maps to which process
- Error-prone when working with multiple processes

### Proposed Solution
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

## 3. Command Aliases

### Current Issues
- Commands are verbose for common operations
- Not aligned with familiar Unix conventions

### Proposed Solution
```bash
# Add familiar aliases
climux ls     # alias for 'list'
climux ps     # alias for 'list' (like Unix ps)

# Future possibilities:
climux rm     # alias for 'stop'
climux exec   # alias for 'send'
```

## 4. Improved List Output

### Current Issues
- Output format could be cleaner
- No JSON output for scripting
- Uptime strings can be very long

### Proposed Solution
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

## 5. Global Operations

### Current Issues
- Can't see logs from all processes at once
- No way to monitor system-wide activity

### Proposed Solution
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

## 6. Simplify Commands

### Current Issues
- `tail` vs `logs` confusion
- `snapshot` command unclear purpose
- Too many ways to view logs

### Proposed Solution
- Remove `tail` command (replace with `logs --tail`)
- Remove or clarify `snapshot` (maybe rename to `last` or integrate into `logs`)
- Consolidate log viewing into single `logs` command with flags

## 7. Better Error Messages

### Current Issues
- "Process 5 not found" - not helpful if using names
- Generic "Failed to start process" without details

### Proposed Solution
```bash
# More helpful error messages
$ climux stop frontend
Error: No process named 'frontend' found

$ climux stop 99
Error: No process with ID 99 found

$ climux start invalid-command
Error: Failed to start process: Command 'invalid-command' not found
```

## Implementation Priority

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

## Backward Compatibility

All changes should be backward compatible:
- Numeric IDs continue to work
- Existing commands remain available
- New features are additions, not replacements

## Example Usage After Improvements

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