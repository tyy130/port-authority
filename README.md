# Port Authority

A centralized port allocation system for managing ports across multiple projects. Instead of projects randomly picking ports or scanning for unused ones, they request allocations from Port Authority.

## Features

- **Centralized allocation**: Single source of truth for port assignments
- **Project isolation**: Track which project owns which port
- **Pool management**: Configure port ranges for different services
- **REST API**: Query via HTTP
- **CLI tool**: Command-line interface for quick lookups
- **Persistent state**: JSON-based registry survives restarts
- **Agent-friendly**: Easy integration with Claude Code and scripts

## Quick Start

### Installation

```bash
git clone https://github.com/tyy130/port-authority.git ~/.local/src/port-authority
cd ~/.local/src/port-authority
pip install -r requirements.txt
./install.sh  # Sets up systemd service
```

### Usage

**Request a port:**

```bash
port-request myproject myservice
# Output: 3000
```

**Release a port:**

```bash
port-release myproject myservice
```

**Check all allocations:**

```bash
port-status
```

**Check specific project:**

```bash
port-status myproject
```

## Configuration

Edit `~/.config/port-authority/config.yaml`:

```yaml
pools:
  web:
    range: [3000, 4000]
    description: "Web services, APIs"
  database:
    range: [5000, 6000]
    description: "Database ports"
  internal:
    range: [8000, 9000]
    description: "Internal services"

# Default pool if not specified
default_pool: web
```

## Integration

### Bash/CLI

```bash
PORT=$(port-request myproject myservice)
echo "Starting on port $PORT"
```

### Python

```python
from port_authority import request_port, release_port

port = request_port("myproject", "myservice")
print(f"Running on port {port}")

# When done:
release_port("myproject", "myservice")
```

### Node.js

```javascript
const { requestPort, releasePort } = require("port-authority");

const port = await requestPort("myproject", "myservice");
console.log(`Running on port ${port}`);

// When done:
await releasePort("myproject", "myservice");
```

### Claude Code / Agents

```bash
# In your project hooks or scripts:
PORT=$(port-request my-project my-service)
```

## Architecture

- **Daemon**: `port-authority-daemon` (systemd service)
- **State**: `~/.local/share/port-authority/allocations.json`
- **API**: REST on Unix socket `~/.local/run/port-authority.sock`
- **CLI**: `port-request`, `port-release`, `port-status`

## License

MIT
