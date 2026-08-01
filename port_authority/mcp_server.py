#!/usr/bin/env python3
"""MCP server exposing Port Authority to any MCP-compatible client (Claude
Desktop, Claude Code, or anything else that speaks Model Context Protocol) --
not just Claude Code's .claude/ skill convention, which only that one client
understands.

This is a thin adapter: every tool delegates to the same HTTP client functions
the CLI already uses (port_authority.request_port / release_port / get_status
/ gc), so auth, error messages, and behavior are identical across the CLI, the
Python library, and this MCP surface -- nothing is reimplemented here.

Requires the optional `mcp` dependency (pip install -r requirements-mcp.txt
or pip install "port-authority[mcp]"), not installed by the base install.sh.
"""

import sys
from pathlib import Path

# Allow running this file directly (e.g. registered as an MCP server command)
# without the package being pip-installed: put the repo root on sys.path so
# the sibling "port_authority" package resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server import MCPServer

import port_authority

mcp = MCPServer(
    "Port Authority",
    instructions=(
        "Allocates ports for local services instead of guessing or hardcoding "
        "one. Call request_port before starting any service that needs a "
        "listening port."
    ),
)


@mcp.tool()
def request_port(project: str, service: str, pool: str = "web") -> str:
    """Request a port for a project/service from Port Authority.

    Idempotent: calling it again for the same project+service returns the
    same port, whether or not the service is currently running. Call this
    BEFORE starting a service instead of hardcoding or guessing a port
    number -- Port Authority verifies the port is actually free on the
    machine, not just unclaimed in its own records. If `service` is a
    recognized name (postgres, redis, mysql, mongodb, ...) it tries that
    service's standard port first, falling back to the pool range if taken.
    """
    port = port_authority.request_port(project, service, pool)
    return f"Allocated port {port} for {project}:{service}"


@mcp.tool()
def release_port(project: str, service: str) -> str:
    """Release a port allocation once the service using it has stopped."""
    if port_authority.release_port(project, service):
        return f"Released {project}:{service}"
    return f"No allocation found for {project}:{service}"


@mcp.tool()
def port_status(project: str = "") -> str:
    """Show current port allocations, optionally filtered to one project.

    Each entry includes whether something is actually listening on the port
    right now (active) or the allocation is idle (service not started, or
    stopped without releasing).
    """
    status = port_authority.get_status(project or None)
    if not status:
        return "No allocations"
    lines = [
        f"{key}: port {info['port']} ({info['pool']}, "
        f"{'active' if info['active'] else 'idle'})"
        for key, info in sorted(status.items())
    ]
    return "\n".join(lines)


@mcp.tool()
def port_gc(force: bool = False) -> str:
    """Preview (default) or actually reclaim (force=True) allocations that
    have been idle longer than the configured grace period.
    """
    released = port_authority.gc(force)
    if not released:
        return "Nothing stale enough to reclaim"
    verb = "Reclaimed" if force else "Would reclaim (call again with force=True to release)"
    lines = [
        f"{verb}: {r['key']} (port {r['port']}, idle "
        f"{int(r['free_for_seconds'] // 60)}m)"
        for r in released
    ]
    return "\n".join(lines)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
