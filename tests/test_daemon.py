"""Tests for the PortAuthority allocation logic.

Each test points STATE_FILE/CONFIG_FILE at a temp dir before constructing
PortAuthority, since the class reads them at __init__ time.
"""
import json
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from port_authority import daemon as daemon_module
from port_authority.daemon import PortAuthority, is_port_free


@pytest.fixture
def authority(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon_module, 'STATE_FILE', tmp_path / 'allocations.json')
    monkeypatch.setattr(daemon_module, 'CONFIG_FILE', tmp_path / 'config.yaml')
    return PortAuthority()


def test_request_port_returns_int_in_pool_range(authority):
    port = authority.request_port('proj', 'svc', pool='web')
    assert isinstance(port, int)
    assert 3000 <= port <= 4000


def test_request_port_is_idempotent(authority):
    first = authority.request_port('proj', 'svc')
    second = authority.request_port('proj', 'svc')
    assert first == second


def test_different_services_get_different_ports(authority):
    a = authority.request_port('proj', 'web')
    b = authority.request_port('proj', 'api', pool='web')
    assert a != b


def test_unknown_pool_returns_error(authority):
    result = authority.request_port('proj', 'svc', pool='does-not-exist')
    assert 'error' in result


def test_invalid_names_rejected(authority):
    assert 'error' in authority.request_port('proj:evil', 'svc')
    assert 'error' in authority.request_port('proj', '')
    assert 'error' in authority.request_port('', 'svc')


def test_release_frees_the_registry_entry(authority):
    authority.request_port('proj', 'svc')
    assert authority.release_port('proj', 'svc') is True
    assert authority.get_status('proj') == {}


def test_release_unknown_returns_false(authority):
    assert authority.release_port('nope', 'nope') is False


def test_skips_ports_already_bound_outside_the_registry(authority):
    # Force the pool down to a single port, then occupy it externally so the
    # daemon's only choice is a port it did NOT hand out itself. Set this on
    # the instance only -- mutating the class's _default_pools would leak
    # into every other test that constructs a fresh PortAuthority().
    authority.pools = {'web': {'range': [40000, 40001], 'description': 'test'}}

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(('127.0.0.1', 40000))
    blocker.listen(1)
    try:
        assert not is_port_free(40000)
        port = authority.request_port('proj', 'svc')
        assert port == 40001
    finally:
        blocker.close()


def test_state_persists_across_instances(tmp_path, monkeypatch):
    state_file = tmp_path / 'allocations.json'
    monkeypatch.setattr(daemon_module, 'STATE_FILE', state_file)
    monkeypatch.setattr(daemon_module, 'CONFIG_FILE', tmp_path / 'config.yaml')

    a1 = PortAuthority()
    port = a1.request_port('proj', 'svc')

    assert json.loads(state_file.read_text())['proj:svc']['port'] == port

    a2 = PortAuthority()
    assert a2.request_port('proj', 'svc') == port


def test_idempotent_lookup_does_not_evict_a_running_service(authority):
    """Regression test: a prior version re-checked is_port_free() on the
    cached-allocation path, and since a service that's actually running IS
    bound to its port (is_port_free -> False), it misread "healthy and
    running" as "stolen by something else" and silently handed the caller a
    DIFFERENT port on every subsequent lookup. The registry must be trusted
    as the source of truth for ownership regardless of live bind state."""
    port = authority.request_port('proj', 'svc')

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(('127.0.0.1', port))
    holder.listen(1)
    try:
        assert not is_port_free(port)  # the "service" is now genuinely running
        again = authority.request_port('proj', 'svc')
        assert again == port
    finally:
        holder.close()


def test_get_status_reports_live_active_flag(authority):
    port = authority.request_port('proj', 'svc')
    assert authority.get_status('proj')['proj:svc']['active'] is False

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(('127.0.0.1', port))
    holder.listen(1)
    try:
        assert authority.get_status('proj')['proj:svc']['active'] is True
    finally:
        holder.close()


def test_sweep_stale_dry_run_never_mutates(authority):
    authority.request_port('proj', 'svc')
    before = json.dumps(authority.allocations, sort_keys=True)

    released = authority.sweep_stale(dry_run=True, now=time.time() + 100_000)

    assert released == []  # free_since was never seeded by a real sweep
    assert json.dumps(authority.allocations, sort_keys=True) == before


def test_sweep_stale_reclaims_only_after_grace_period(authority):
    authority.stale_after_minutes = 10
    authority.request_port('proj', 'svc')
    t0 = time.time()

    # First real sweep: port is free, nothing tracked yet -> starts the clock,
    # does not reclaim.
    assert authority.sweep_stale(dry_run=False, now=t0) == []
    assert 'proj:svc' in authority.allocations

    # Still within the grace period.
    assert authority.sweep_stale(dry_run=False, now=t0 + 5 * 60) == []
    assert 'proj:svc' in authority.allocations

    # Past the grace period -> reclaimed.
    released = authority.sweep_stale(dry_run=False, now=t0 + 11 * 60)
    assert [r['key'] for r in released] == ['proj:svc']
    assert 'proj:svc' not in authority.allocations


def test_sweep_stale_clears_timer_once_port_is_bound_again(authority):
    authority.stale_after_minutes = 10
    port = authority.request_port('proj', 'svc')
    t0 = time.time()

    authority.sweep_stale(dry_run=False, now=t0)  # starts the free_since clock
    assert authority.allocations['proj:svc'].get('free_since') == t0

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(('127.0.0.1', port))
    holder.listen(1)
    try:
        authority.sweep_stale(dry_run=False, now=t0 + 5 * 60)
    finally:
        holder.close()

    assert 'free_since' not in authority.allocations['proj:svc']
    # Long after, with the port free again but the timer reset, it should
    # NOT be reclaimed yet -- it needs a fresh grace period.
    assert authority.sweep_stale(dry_run=False, now=t0 + 20 * 60) == []
    assert 'proj:svc' in authority.allocations


def _free_port():
    """Ask the OS for a currently-unused port. Real default service ports
    (5432, 6379, ...) can't be trusted to be free on a real dev machine --
    this box had postgres, redis, AND an unrelated process on 8765 all
    genuinely occupied while writing these tests, so hardcoding "probably
    free" numbers is not safe here."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_known_service_gets_its_canonical_port(authority):
    port = _free_port()
    authority.known_services['test-db'] = port
    assert authority.request_port('proj', 'test-db') == port


def test_known_service_match_is_case_insensitive(authority):
    port = _free_port()
    authority.known_services['test-db'] = port
    assert authority.request_port('proj', 'Test-DB') == port


def test_known_service_aliases_map_to_the_same_port():
    # Two DIFFERENT projects requesting two alias names for the same
    # canonical port is a genuine collision (same as any other port
    # collision) -- the second one correctly falls back rather than
    # double-allocating, so that's not what this checks. This is a plain
    # data check that the alias table itself is internally consistent.
    from port_authority.daemon import DEFAULT_KNOWN_SERVICES

    assert DEFAULT_KNOWN_SERVICES['postgres'] == DEFAULT_KNOWN_SERVICES['postgresql'] == DEFAULT_KNOWN_SERVICES['pg'] == 5432
    assert DEFAULT_KNOWN_SERVICES['mysql'] == DEFAULT_KNOWN_SERVICES['mariadb'] == 3306
    assert DEFAULT_KNOWN_SERVICES['mongodb'] == DEFAULT_KNOWN_SERVICES['mongo'] == 27017


def test_unrecognized_service_name_uses_normal_pool_scan(authority):
    # 'svc' isn't a known service -- falls straight through to pool scanning,
    # same as before this feature existed.
    port = authority.request_port('proj', 'svc')
    assert 3000 <= port <= 4000


def test_known_service_falls_back_to_pool_when_canonical_port_is_taken(authority):
    port = _free_port()
    authority.known_services['test-db'] = port

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(('127.0.0.1', port))
    blocker.listen(1)
    try:
        result = authority.request_port('proj', 'test-db')
        assert result != port
        assert 3000 <= result <= 4000  # fell back to the 'web' pool default
    finally:
        blocker.close()


def test_known_service_falls_back_when_canonical_port_already_allocated(authority):
    port = _free_port()
    authority.known_services['test-db'] = port

    first = authority.request_port('proj-a', 'test-db')
    assert first == port

    second = authority.request_port('proj-b', 'test-db')
    assert second != port
    assert 3000 <= second <= 4000


def test_config_can_add_and_override_known_services(tmp_path, monkeypatch):
    monkeypatch.setattr(daemon_module, 'STATE_FILE', tmp_path / 'allocations.json')
    override_port = _free_port()
    new_service_port = _free_port()
    config_file = tmp_path / 'config.yaml'
    config_file.write_text(
        'known_services:\n'
        f'  postgres: {override_port}\n'  # override a default
        f'  my-custom-tool: {new_service_port}\n'  # add a new one
    )
    monkeypatch.setattr(daemon_module, 'CONFIG_FILE', config_file)

    authority = PortAuthority()
    assert authority.request_port('proj', 'postgres') == override_port
    assert authority.request_port('proj', 'my-custom-tool') == new_service_port
    # Unrelated defaults survive a partial override -- structural check, not
    # a live allocation, since we can't assume 6379 is actually free here.
    assert authority.known_services['redis'] == 6379
