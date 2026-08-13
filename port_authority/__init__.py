"""Port Authority - Centralized port allocation."""

import requests

from port_authority._config import API_URL, auth_headers


def request_port(project, service, pool='web'):
    """Request a port from Port Authority.

    Args:
        project: Project name
        service: Service name
        pool: Port pool to allocate from (default: web)

    Returns:
        int: Allocated port number

    Raises:
        Exception: If daemon not running or error occurs
    """
    try:
        resp = requests.get(f'{API_URL}/request', params={
            'project': project,
            'service': service,
            'pool': pool,
        }, headers=auth_headers(), timeout=2)
        data = resp.json()

        if 'error' in data:
            raise Exception(data['error'])

        return data['port']
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running. Start it with: port-authority-daemon")


def release_port(project, service):
    """Release an allocated port.

    Args:
        project: Project name
        service: Service name

    Returns:
        bool: True if successful
    """
    try:
        resp = requests.get(f'{API_URL}/release', params={
            'project': project,
            'service': service,
        }, headers=auth_headers(), timeout=2)
        data = resp.json()

        if 'error' in data:
            raise Exception(data['error'])

        return data.get('success', False)
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running")


def get_status(project=None):
    """Get current port allocations.

    Args:
        project: Optional project name to filter by

    Returns:
        dict: Allocation status, each entry annotated with 'active' (bool)
    """
    try:
        params = {'project': project} if project else {}
        resp = requests.get(f'{API_URL}/status', params=params, headers=auth_headers(), timeout=2)
        data = resp.json()

        if 'error' in data:
            raise Exception(data['error'])

        return data
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running")


def gc(force=False):
    """Preview (default) or perform reclamation of long-stale allocations.

    Args:
        force: If True, actually release stale allocations. If False
            (default), only report what a real sweep would release.

    Returns:
        list: Allocations released (or that would be released)
    """
    try:
        resp = requests.get(f'{API_URL}/gc', params={
            'dry_run': 'false' if force else 'true',
        }, headers=auth_headers(), timeout=5)
        data = resp.json()

        if 'error' in data:
            raise Exception(data['error'])

        return data['released']
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running")


__all__ = ['request_port', 'release_port', 'get_status', 'gc']
