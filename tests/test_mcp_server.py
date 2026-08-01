"""End-to-end check that the MCP tool layer actually works, not just that it
imports. Each tool is a thin wrapper around the same client functions the CLI
uses, so this spins up a real daemon HTTP server (same pattern as
test_http_auth.py) and drives the tools through mcp_server.mcp.call_tool() --
the same programmatic entry point the MCP framework itself uses to dispatch a
real tool call, just without a subprocess/stdio round trip.
"""
import asyncio
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

pytest.importorskip("mcp")  # optional dependency -- skip cleanly if not installed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import port_authority
from port_authority import daemon as daemon_module
from port_authority.daemon import PortAuthority, RequestHandler
from port_authority import mcp_server


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon_module, 'STATE_FILE', tmp_path / 'allocations.json')
    monkeypatch.setattr(daemon_module, 'CONFIG_FILE', tmp_path / 'config.yaml')

    RequestHandler.authority = PortAuthority()
    RequestHandler.token = 'mcp-test-token'

    token_file = tmp_path / 'token'
    token_file.write_text('mcp-test-token')
    monkeypatch.setattr('port_authority._config.TOKEN_FILE', token_file)

    server = HTTPServer(('127.0.0.1', 0), RequestHandler)
    monkeypatch.setattr(port_authority, 'API_URL', f'http://127.0.0.1:{server.server_port}')

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        thread.join(timeout=2)


def call(name, **kwargs):
    return asyncio.run(mcp_server.mcp.call_tool(name, kwargs))


def text_of(result):
    return result.content[0].text


def test_request_port_tool_allocates_and_reports_it(live_server):
    result = call('request_port', project='proj', service='svc')
    assert result.is_error is not True
    assert 'proj:svc' in text_of(result)
    assert 'Allocated port' in text_of(result)


def test_request_port_tool_is_idempotent(live_server):
    first = text_of(call('request_port', project='proj', service='svc'))
    second = text_of(call('request_port', project='proj', service='svc'))
    assert first == second


def test_status_tool_reflects_allocations(live_server):
    call('request_port', project='proj', service='svc')
    status = text_of(call('port_status'))
    assert 'proj:svc' in status
    assert 'idle' in status  # nothing is actually bound to the port


def test_status_tool_filters_by_project(live_server):
    call('request_port', project='proj-a', service='svc')
    call('request_port', project='proj-b', service='svc')
    status = text_of(call('port_status', project='proj-a'))
    assert 'proj-a:svc' in status
    assert 'proj-b:svc' not in status


def test_release_tool_frees_the_allocation(live_server):
    call('request_port', project='proj', service='svc')
    released = text_of(call('release_port', project='proj', service='svc'))
    assert 'Released proj:svc' in released
    assert text_of(call('port_status')) == 'No allocations'


def test_release_tool_reports_unknown_allocation(live_server):
    result = text_of(call('release_port', project='nope', service='nope'))
    assert 'No allocation found' in result


def test_gc_tool_reports_nothing_stale_on_fresh_allocation(live_server):
    call('request_port', project='proj', service='svc')
    result = text_of(call('port_gc'))
    assert 'Nothing stale' in result


def test_invalid_project_name_surfaces_as_tool_error(live_server):
    # call_tool() is the programmatic entry point (what this test suite uses to
    # invoke tools directly) -- it re-raises a failed tool as ToolError rather
    # than returning CallToolResult(is_error=True). Over the real stdio/wire
    # protocol the framework's own request handler catches this and reports it
    # to the client as a normal tool-call error instead of crashing the server;
    # that conversion is the SDK's job, not something this test can observe
    # without spinning up a full subprocess/stdio round trip.
    from mcp.server.mcpserver.exceptions import ToolError

    with pytest.raises(ToolError, match='project/service must be non-empty'):
        call('request_port', project='bad:name', service='svc')
