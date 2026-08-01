"""End-to-end check that the HTTP layer actually enforces the auth token.

Unit tests on PortAuthority never touch RequestHandler, so they can't catch
a broken or missing auth check. This spins up a real HTTPServer on an
OS-assigned free port and hits it with urllib.
"""
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from port_authority import daemon as daemon_module
from port_authority.daemon import PortAuthority, RequestHandler


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon_module, 'STATE_FILE', tmp_path / 'allocations.json')
    monkeypatch.setattr(daemon_module, 'CONFIG_FILE', tmp_path / 'config.yaml')

    RequestHandler.authority = PortAuthority()
    RequestHandler.token = 'test-token-123'

    server = HTTPServer(('127.0.0.1', 0), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _get(url, token=None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    req = Request(url, headers=headers)
    return urlopen(req, timeout=2)


def test_request_without_token_is_rejected(live_server):
    with pytest.raises(HTTPError) as exc_info:
        _get(f'{live_server}/status')
    assert exc_info.value.code == 401


def test_request_with_wrong_token_is_rejected(live_server):
    with pytest.raises(HTTPError) as exc_info:
        _get(f'{live_server}/status', token='not-the-right-token')
    assert exc_info.value.code == 401


def test_request_with_correct_token_succeeds(live_server):
    resp = _get(f'{live_server}/status', token='test-token-123')
    assert resp.status == 200
    assert json.loads(resp.read()) == {}


def test_request_allocates_a_real_port_end_to_end(live_server):
    resp = _get(f'{live_server}/request?project=proj&service=svc', token='test-token-123')
    data = json.loads(resp.read())
    assert 3000 <= data['port'] <= 4000
