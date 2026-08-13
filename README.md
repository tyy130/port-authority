# Port Authority

[![Tests](https://github.com/tyy130/port-authority/actions/workflows/test.yml/badge.svg)](https://github.com/tyy130/port-authority/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/portauth)](https://pypi.org/project/portauth/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](setup.py)

A small local daemon that hands out ports on request instead of every project guessing or scanning for a free one. One project asks "give me a port for `web`," another asks for `api`, and Port Authority makes sure they never collide — including with things it didn't allocate (Docker containers, stray processes, anything already bound).

## Features

- **Centralized allocation**: one registry instead of every project picking its own port
- **Real availability checks**: before handing out a port, the daemon actually tries to bind it — not just "not in my registry"
- **Token auth**: the daemon generates a local secret on first start; the CLI/library read it automatically — no plaintext-anyone-on-the-box access
- **Stale-allocation cleanup**: a background sweep reclaims ports whose owner crashed and never released them, after a configurable grace period — plus `port gc` to preview or force it on demand
- **Pool management**: configurable ranges per category (web, api, database, ...)
- **Known services**: `port myproject postgres` tries port 5432 first (falling back to the normal pool scan if it's taken) — covers common databases, caches, and brokers out of the box, extendable via config
- **REST API**: plain HTTP on `127.0.0.1:8888`
- **CLI + Python library**: use from shell scripts or import directly
- **Persistent state**: allocations survive daemon restarts (`~/.local/share/port-authority/allocations.json`)
- **Agent-friendly**: ships a Claude Code skill + `CLAUDE.md` snippet (no extra dependencies) _and_ a real [MCP server](#mcp-server-any-mcp-client) (optional dependency) so any MCP-compatible agent — not just Claude Code — can call it as a native tool
- **Cross-platform auto-start**: systemd user service on Linux, launchd agent on macOS, both installed and started by `install.sh`; CI runs the full suite on both `ubuntu-latest` and `macos-latest`

## Quick Start

### Installation

```bash
git clone https://github.com/tyy130/port-authority.git
cd port-authority
./install.sh
```

`install.sh` installs the Python deps, symlinks the CLI into `~/.local/bin`, writes a default config, and installs + starts the daemon as a background service — a systemd user unit on Linux, a launchd agent on macOS. Falls back to printing manual-start instructions if neither is available.

Make sure `~/.local/bin` is on your `PATH`.

Prefer `pip`? `pip install portauth` gets you the CLI and library (published as `portauth` — see [why](setup.py)), but you're on your own for starting the daemon (`port-authority-daemon &`) and keeping it running, since `install.sh` is what wires up the systemd/launchd service.

### Usage

```bash
# Friendly wrapper — request a port
port myproject myservice
# -> 3005

# Same thing via the full CLI
port-request request myproject myservice --pool web

# Release it when the service stops
port-request release myproject myservice

# See everything currently allocated (with live active/inactive status)
port status
port-request status --project myproject

# Preview allocations that would be reclaimed as stale, or force it now
port gc
port gc --force
```

Project and service names must match `[A-Za-z0-9_-]+` — no colons or slashes, since names get embedded in the registry key.

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

default_pool: web

# How long a port can sit allocated-but-unbound before the background
# sweep (and `port gc --force`) reclaim it.
stale_after_minutes: 60

# Extend or override the built-in known-service ports (postgres, redis,
# mysql, mongodb, and a couple dozen other common dev services -- see
# DEFAULT_KNOWN_SERVICES in port_authority/daemon.py for the full list).
# Requesting a port for one of these names tries the given port first,
# falling back to normal pool scanning if it's taken.
known_services:
  postgres: 5432 # overrides the built-in default
  my-internal-tool: 7777 # adds a new one
```

Changes require restarting the daemon (`systemctl --user restart port-authority` on Linux, `launchctl kickstart -k gui/$(id -u)/com.portauthority.daemon` on macOS).

## Integration

### Bash

```bash
PORT=$(port myproject myservice)
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

### Claude Code / Agents

Copy `.claude/CLAUDE.md` from this repo into your project (or `@`-reference it) so agents working in that codebase default to requesting a port instead of hardcoding `3000`. See [INTEGRATION.md](INTEGRATION.md) for the full setup, including an optional pre-commit hook that flags hardcoded ports in diffs.

### MCP server (any MCP client)

The `.claude/` convention above only means anything to Claude Code — it's a file another tool has no reason to look at. For every other MCP-compatible client (Claude Desktop, other agent frameworks), Port Authority also ships as a real [MCP](https://modelcontextprotocol.io) server exposing `request_port`, `release_port`, `port_status`, and `port_gc` as native tools, over the standard stdio transport.

This is an optional dependency (requires Python 3.10+; the base install works on 3.9+ and stays stdlib-only otherwise):

```bash
pip install -r requirements-mcp.txt   # or: pip install "portauth[mcp]"
```

Register it with any MCP client by pointing at the script (adjust the path to your clone):

```json
{
  "mcpServers": {
    "port-authority": {
      "command": "python3",
      "args": ["/path/to/port-authority/port_authority/mcp_server.py"]
    }
  }
}
```

The tools call the exact same HTTP client the CLI uses (`port_authority.request_port` etc.) — same auth, same error messages, same behavior, just exposed over MCP instead of the command line.

## Architecture

- **Daemon**: `port-authority-daemon` — a single-threaded `http.server` on `127.0.0.1:8888` (not exposed beyond localhost), plus a background thread that sweeps for stale allocations every 60s
- **Auth**: a random token minted on first daemon start, stored at `~/.config/port-authority/token` (`0600`), required as a Bearer token on every request
- **State**: `~/.local/share/port-authority/allocations.json`
- **CLI**: `port` (friendly wrapper) / `port-request` (full subcommands: `request`, `release`, `status`, `gc`)
- **MCP server**: `port_authority/mcp_server.py` (`port-authority-mcp` once installed) — optional, thin adapter over the same client the CLI uses

## How allocation ownership works

The registry is the source of truth for _who owns a port_, not whether it's currently bound. A healthy running service IS bound to its port — that's expected, not a conflict. So:

- **Looking up an existing allocation** (`port myproject myservice` called again) always returns the same port, regardless of whether it's currently active or idle.
- **Picking a brand-new port** for a key that isn't in the registry tries the service's canonical port first if it's a known one (see [Configuration](#configuration)), then skips anything currently bound — whether Port Authority knows about it or not — while scanning the pool range.
- **Reclaiming an abandoned allocation** (owner crashed, never called `release`) only happens after the port has been continuously free for `stale_after_minutes` — a service that just hasn't started yet is never mistaken for a dead one.

## Known limitations

- **Single machine.** There's no clustering or shared state across hosts — each machine runs its own daemon and registry.
- **Trust model is "anyone who can read your dotfiles."** The token is a local secret file, not real per-caller identity — it stops a stray unprivileged process from guessing its way in, not a determined actor already on your account.

## License

MIT
