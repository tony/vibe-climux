# Climux

A headless CLI process manager that bridges the gap between human developers and AI agents. Run background processes with the simplicity of `tmux` but with JSON-RPC control that AI can understand.

## The Problem Climux Solves

**For Developers:** You're juggling 5+ terminal windows - frontend, backend, database, tests, and logs. Alt-tabbing constantly. Losing track of what's running where. Missing important error messages in the chaos.

**For AI Agents:** Current tools aren't built for programmatic control. Agents struggle with terminal emulators, can't reliably parse unstructured output, and have no way to manage long-running processes.

**Climux:** One tool that works perfectly for both humans and machines.

## Why Climux?

### 🚀 For Local Development

Transform this common scenario:
```bash
# Terminal 1: Frontend
npm run dev

# Terminal 2: Backend  
python manage.py runserver

# Terminal 3: Database
docker-compose up postgres

# Terminal 4: Redis
redis-server

# Terminal 5: Tests
npm run test:watch

# Terminal 6: Where did that error come from?!
```

Into this:
```bash
# Just start using climux - no server setup needed!
climux start npm run dev --name frontend
climux start python manage.py runserver --name backend
climux start docker-compose up postgres --name db
climux start redis-server --name redis
climux start npm run test:watch --name tests

# Now you have superpowers
climux list                    # What's running?
climux tail backend            # Watch backend logs
climux logs frontend --lines 50 # What just happened?
climux restart backend         # Quick restart
climux send tests "r\n"        # Re-run tests
```

**Benefits:**
- 📊 Single dashboard for all processes
- 🔍 Never lose important logs
- ⚡ Instant access to any process
- 🔄 Easy restarts without finding the right terminal
- 📝 Searchable history across all processes

### 🤖 For AI/Agent Workflows

Climux speaks JSON-RPC, making it the perfect bridge between AI and system processes:

```python
# AI agents can now control processes like a senior developer
async def deploy_and_monitor(client: ClimuxClient):
    # Start the deployment
    deploy = await client.request("start", {
        "command": ["./deploy.sh", "production"],
        "name": "deployment"
    })
    
    # Watch for completion or errors
    while True:
        logs = await client.request("logs", {
            "id": deploy["id"], 
            "lines": 10
        })
        
        # AI can understand structured output
        for log in logs:
            if "ERROR" in log["content"]:
                # Intelligent error handling
                await handle_deployment_error(log)
                break
            elif "Deployment complete" in log["content"]:
                # Success! Start monitoring
                await start_monitoring(client)
                break
                
        await asyncio.sleep(5)
```

**Why it's perfect for AI:**
- 📋 Structured JSON responses (not raw terminal chaos)
- 🎯 Precise process control (start, stop, restart, send input)
- 📊 Reliable log parsing with timestamps and sources
- 🔄 Stateless operations (no terminal state to manage)
- 🛡️ Safe interaction (can't accidentally break the terminal)

## Core Features

- **Implicit Server Start**: Like tmux, the server starts automatically when needed
- **Standard Library Only**: Zero dependencies, works with Python 3.13+
- **JSON-RPC 2.0**: Structured communication protocol that's LLM-friendly
- **Full Process Control**: Start, stop, restart, send input, capture output
- **Smart Buffering**: Configurable line and time-based log retention
- **Guaranteed Cleanup**: PID journaling ensures no orphaned processes
- **Asyncio-based**: Efficient concurrent process management
- **Type-Safe**: Fully typed for better IDE support and fewer bugs

## 10-Second Pitch

**Without Climux:**
- 🪟 Alt-tab between 10 terminal windows
- 😵 Lose track of which process is which
- 🔍 Scroll through walls of logs to find that one error
- 🔄 Kill and restart processes manually
- 🤖 AI agents can't help - they can't control terminals

**With Climux:**
- 📋 `climux list` - See everything at a glance
- 🎯 `climux tail backend` - Jump to any process instantly  
- 📊 `climux logs api --lines 50` - Get exactly what you need
- ⚡ `climux restart frontend` - One command, done
- 🤝 AI agents can manage your dev environment for you

## Quick Start

```bash
# Install development environment
uv sync --all-extras --dev

# Just start using climux - server starts automatically!
climux start python -m http.server 8000 --name webserver
climux list
climux logs webserver
```

## Real-World Use Cases

### 💻 Local Development Workflows

#### The "Full Stack Startup" Script
Save this as `dev.sh` and never juggle terminals again:
```bash
#!/bin/bash
# Climux starts automatically - no setup needed!

# Start your entire stack
climux start npm run dev --name frontend --cwd ./frontend
climux start python manage.py runserver --name api --cwd ./backend  
climux start docker-compose up postgres redis --name services
climux start npm run test:watch --name tests --cwd ./frontend
climux start python manage.py celery worker --name worker --cwd ./backend

echo "🚀 Dev environment ready!"
echo "Commands:"
echo "  climux list          - See all processes"
echo "  climux tail <name>   - Follow logs"
echo "  climux restart <name> - Restart a service"
echo "  ./dev.sh stop        - Stop everything"

if [ "$1" = "stop" ]; then
    for id in $(climux list | grep -o '^[0-9]*'); do
        climux stop $id
    done
fi
```

#### Debugging Production Issues Locally
```bash
# Reproduce production environment locally
climux start python app.py --name api --env ENVIRONMENT=staging
climux start node worker.js --name worker --env ENVIRONMENT=staging
climux start redis-server --config redis.prod.conf --name redis

# Reproduce the issue
climux send api "trigger_bug_endpoint\n"

# Capture everything
climux logs api --lines 1000 > api_debug.log
climux logs worker --lines 1000 > worker_debug.log

# Interactive debugging
climux send api "import pdb; pdb.set_trace()\n"
climux tail api  # Now you can debug interactively!
```

#### Microservices Development
```bash
# Start 10 microservices without 10 terminals
for service in auth user product cart payment shipping inventory search recommendation analytics; do
    climux start npm run dev --name $service --cwd ./services/$service
done

# Health check all services
for service in $(climux list | awk '{print $2}' | grep -v "name"); do
    echo "Checking $service..."
    climux logs $service --lines 5 | grep -q "Ready" && echo "✅ $service is ready"
done

# Restart a specific service after code changes
climux restart cart

# See which services are consuming most resources
climux list  # Shows PIDs
# Use htop/top to monitor those specific PIDs
```

### 🤖 AI Agent Workflows

#### Autonomous Development Assistant
```python
class DevAssistant:
    """AI assistant that manages your development environment."""
    
    def __init__(self, climux_client):
        self.client = climux_client
        self.processes = {}
    
    async def setup_project(self, project_type: str):
        """Intelligently set up a development environment."""
        if project_type == "django":
            # Start database first
            db = await self.client.request("start", {
                "command": ["docker", "run", "-p", "5432:5432", "postgres"],
                "name": "database"
            })
            
            # Wait for database to be ready
            await self.wait_for_log(db["id"], "database system is ready")
            
            # Run migrations
            migrate = await self.client.request("start", {
                "command": ["python", "manage.py", "migrate"],
                "name": "migrations"
            })
            await self.wait_for_completion(migrate["id"])
            
            # Start the dev server
            server = await self.client.request("start", {
                "command": ["python", "manage.py", "runserver"],
                "name": "django-server"
            })
            
            return "✅ Django environment ready at http://localhost:8000"
    
    async def diagnose_issue(self, error_description: str):
        """Analyze logs across all processes to diagnose issues."""
        all_processes = await self.client.request("list")
        
        for proc in all_processes:
            if proc["status"] == "exited" and proc["exit_code"] != 0:
                # Get error logs
                logs = await self.client.request("logs", {
                    "id": proc["id"],
                    "lines": 50
                })
                
                # AI analyzes the logs
                error_analysis = self.analyze_error_logs(logs)
                if error_analysis["confidence"] > 0.8:
                    # Attempt automatic fix
                    await self.apply_fix(proc, error_analysis["solution"])
```

#### Continuous Integration Bot
```python
async def ci_pipeline(client: ClimuxClient, pr_number: int):
    """AI-driven CI pipeline that adapts to project needs."""
    
    # Detect project type and test requirements
    project_files = os.listdir(".")
    test_commands = detect_test_commands(project_files)
    
    # Run all tests in parallel
    test_processes = []
    for cmd in test_commands:
        proc = await client.request("start", {
            "command": cmd.split(),
            "name": f"test-{cmd[0]}"
        })
        test_processes.append(proc)
    
    # Monitor and report results
    results = {}
    for proc in test_processes:
        status = await wait_for_completion(client, proc["id"])
        logs = await client.request("logs", {"id": proc["id"]})
        
        # Parse test results
        results[proc["name"]] = parse_test_output(logs)
    
    # Generate intelligent summary
    return generate_ci_report(results, pr_number)
```

#### Production Monitoring Agent
```python
async def production_monitor(client: ClimuxClient):
    """AI agent that monitors production-like environments."""
    
    # Start monitoring dashboards
    monitors = {
        "logs": await client.request("start", {
            "command": ["tail", "-f", "/var/log/app.log"],
            "name": "log-monitor"
        }),
        "metrics": await client.request("start", {
            "command": ["python", "collect_metrics.py"],
            "name": "metrics-collector"
        }),
        "health": await client.request("start", {
            "command": ["python", "health_check.py"],
            "name": "health-checker"
        })
    }
    
    # Continuous monitoring loop
    while True:
        for name, proc in monitors.items():
            logs = await client.request("logs", {
                "id": proc["id"],
                "lines": 100
            })
            
            # AI analyzes patterns
            anomalies = detect_anomalies(logs)
            if anomalies:
                await handle_production_issue(anomalies)
        
        await asyncio.sleep(30)
```

### 🚀 Quick Productivity Wins

#### One-Liner Dev Environment
```bash
# Add to your .bashrc/.zshrc
alias dev='climux start npm run dev --name fe && climux start python api.py --name be && climux list'
alias dev-stop='climux list | grep -o "^[0-9]*" | xargs -I {} climux stop {}'
alias dev-logs='climux logs $(climux list | fzf | cut -d" " -f1)'
```

#### Git Hook for Automatic Testing
```bash
# .git/hooks/pre-push
#!/bin/bash
climux start pytest --name tests
climux start npm test --name js-tests

# Wait for tests to complete
while climux list | grep -E "tests.*running"; do sleep 1; done

# Check if tests passed
if climux logs tests | grep -q "FAILED"; then
    echo "❌ Tests failed! Push aborted."
    exit 1
fi
```

#### VSCode Task Integration
```json
// .vscode/tasks.json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start Dev Environment",
      "type": "shell",
      "command": "climux start npm run dev --name frontend",
      "problemMatcher": []
    },
    {
      "label": "View Backend Logs",
      "type": "shell",
      "command": "climux tail backend",
      "problemMatcher": []
    }
  ]
}
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