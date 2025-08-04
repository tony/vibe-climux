# Climux

A headless CLI process manager for local development and AI/agent workflows. Think of it as tmux for background processes - no GUI, just JSON-RPC control.

## Why Climux?

### For Local Development
Replace multiple terminal windows with a single process manager:
```bash
# Instead of 5 terminal tabs, use one climux server
climux server &

# Start all your services
climux start npm run dev --name frontend
climux start python api.py --name backend  
climux start docker-compose up db --name database
climux start npm run test:watch --name tests

# Monitor everything from one place
climux list
climux tail backend
climux logs frontend --lines 50
```

### For AI/Agent Workflows
Climux provides structured, parseable control perfect for LLMs and agents:
```python
# Agents can manage processes programmatically
client = ClimuxClient(socket_path)

# Start a long-running process
result = await client.request("start", {
    "command": ["python", "train_model.py"],
    "name": "model-training"
})

# Monitor progress
logs = await client.request("logs", {"id": result["id"], "lines": 10})

# Send commands
await client.request("send", {"id": result["id"], "data": "stop\n"})
```

## Core Features

- **Standard Library Only**: Zero dependencies, works with Python 3.13+
- **JSON-RPC 2.0**: Structured communication protocol that's LLM-friendly
- **Full Process Control**: Start, stop, restart, send input, capture output
- **Smart Buffering**: Configurable line and time-based log retention
- **Guaranteed Cleanup**: PID journaling ensures no orphaned processes
- **Asyncio-based**: Efficient concurrent process management
- **Type-Safe**: Fully typed for better IDE support and fewer bugs

## Quick Start

```bash
# Install development environment
uv sync --all-extras --dev

# Start the server
climux server

# In another terminal, start using climux
climux start python -m http.server 8000 --name webserver
climux list
climux logs webserver
```

## Real-World Examples

### Web Development Setup
```bash
# Start your entire dev environment with one command
climux start npm run dev --name frontend --cwd ./frontend
climux start python manage.py runserver --name django --cwd ./backend
climux start redis-server --name redis
climux start celery worker -A myapp --name celery

# Check what's running
climux list
# [1] frontend: running (PID: 12345)
# [2] django: running (PID: 12346)
# [3] redis: running (PID: 12347)
# [4] celery: running (PID: 12348)

# Debug issues
climux logs django --lines 50
climux tail frontend
```

### Data Science Workflow
```bash
# Start Jupyter and monitor resources
climux start jupyter lab --name jupyter
climux start nvidia-smi -l 1 --name gpu-monitor
climux start htop --name system-monitor

# Run long training jobs
climux start python train.py --epochs 100 --name training
climux tail training  # Watch progress

# Send commands to interactive processes
climux send training "pause\n"  # Pause training
climux send training "resume\n" # Resume training
```

### CI/CD Testing
```bash
# Run multiple test suites in parallel
climux start pytest tests/unit --name unit-tests
climux start pytest tests/integration --name integration-tests  
climux start npm test --name frontend-tests

# Wait for all to complete
while climux list | grep -q "running"; do
    sleep 1
done

# Check results
for id in 1 2 3; do
    echo "=== Process $id logs ==="
    climux logs $id | tail -20
done
```

### Agent Integration Example
```python
import asyncio
from pathlib import Path
from climux import ClimuxClient

async def train_model_with_monitoring():
    """Example of agent-controlled model training."""
    client = ClimuxClient(Path("/tmp/climux/default.sock"))
    
    # Start training
    proc = await client.request("start", {
        "command": ["python", "train.py", "--model", "gpt"],
        "name": "model-training",
        "max_log_lines": 10000
    })
    
    # Monitor training progress
    while True:
        logs = await client.request("logs", {
            "id": proc["id"], 
            "lines": 5
        })
        
        # Check for completion or errors
        last_logs = "\n".join(log["content"] for log in logs)
        if "Training complete" in last_logs:
            break
        elif "ERROR" in last_logs:
            # Handle error
            await client.request("stop", {"id": proc["id"]})
            raise Exception("Training failed")
            
        await asyncio.sleep(10)
    
    # Get final metrics
    final_logs = await client.request("snapshot", {
        "id": proc["id"],
        "lines": 100
    })
    return parse_metrics(final_logs)
```

## Advanced Usage

### Socket Management
```bash
# Use named sockets for different environments
climux -L dev server    # Development environment
climux -L test server   # Test environment
climux -L prod server   # Production monitoring

# Connect to specific socket
climux -L dev list
climux -L test start pytest
```

### Process Configuration
```bash
# Configure log retention
climux start python app.py --name myapp --max-lines 5000 --max-hours 48

# Set working directory
climux start npm start --name frontend --cwd /path/to/frontend

# Pass environment variables
export API_KEY=secret
climux start python api.py --name api
```

### Debugging
```bash
# Get detailed process info
climux list
climux snapshot <id>  # Last 25 lines by default
climux logs <id> --lines 100  # Get more history

# Monitor in real-time
climux tail <id>  # Follow logs (like tail -f)

# Send input to processes
climux send <id> "quit\n"
climux send <id> "reload\n"
```

## Architecture

### Design Principles
- **Standard Library Only**: No external dependencies in production
- **Asyncio-based**: All I/O uses asyncio for efficiency
- **Type-Safe**: Full type annotations with mypy strict mode
- **Testable**: Comprehensive test suite with pytest
- **Clean**: Processes are guaranteed to be cleaned up

### Components
- **Server**: Manages processes and handles JSON-RPC requests
- **Client**: Sends commands to server via Unix socket
- **Process Manager**: Handles subprocess lifecycle with asyncio
- **Log Buffer**: Configurable retention by lines and time
- **PID Journal**: Ensures cleanup even after crashes

### Protocol
Commands use JSON-RPC 2.0 over Unix sockets:
```json
{
  "jsonrpc": "2.0",
  "method": "start",
  "params": {
    "command": ["python", "app.py"],
    "name": "myapp"
  },
  "id": 1
}
```

## Development

### Setup
```bash
# Clone the repository
git clone <repo-url>
cd climux

# Install with uv (recommended)
uv sync --all-extras --dev

# Or with pip
pip install -e ".[dev]"
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_climux.py::TestBasicOperations

# Run tests in parallel
uv run pytest -n auto

# Watch mode for development
uv run pytest-watcher
```

### Code Quality
```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Type check
uv run mypy .

# Run all checks
uv run ruff check . && uv run ruff format . --check && uv run mypy .
```

## Comparison with Alternatives

| Feature | Climux | tmux | pm2 | supervisord |
|---------|---------|------|-----|-------------|
| Headless operation | ✅ | ❌ | ✅ | ✅ |
| Zero dependencies | ✅ | ❌ | ❌ | ❌ |
| JSON-RPC control | ✅ | ❌ | ✅ | ❌ |
| Python native | ✅ | ❌ | ❌ | ✅ |
| Agent-friendly | ✅ | ❌ | ⚠️ | ⚠️ |
| Type-safe | ✅ | ❌ | ❌ | ❌ |

## Contributing

Contributions are welcome! Please ensure:
- All tests pass (`uv run pytest`)
- Code is formatted (`uv run ruff format .`)
- Type checks pass (`uv run mypy .`)
- New features include tests

## License

MIT License - see LICENSE file for details