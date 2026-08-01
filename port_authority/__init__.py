"""Port Authority - Centralized port allocation."""

import requests
import json

API_URL = 'http://127.0.0.1:8888'


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
        }, timeout=2)
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
        }, timeout=2)
        return resp.json().get('success', False)
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running")


def get_status(project=None):
    """Get current port allocations.

    Args:
        project: Optional project name to filter by

    Returns:
        dict: Allocation status
    """
    try:
        params = {'project': project} if project else {}
        resp = requests.get(f'{API_URL}/status', params=params, timeout=2)
        return resp.json()
    except requests.ConnectionError:
        raise Exception("Port Authority daemon not running")


__all__ = ['request_port', 'release_port', 'get_status']
