#!/usr/bin/env python3
"""Port Authority CLI - Command-line interface for port requests."""

import requests
import sys
import argparse
from pathlib import Path

# Allow running this file directly (e.g. symlinked into ~/.local/bin) without
# the package being pip-installed: put the repo root on sys.path so the
# sibling "port_authority" package resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from port_authority._config import API_URL, auth_headers


def _headers_or_exit():
    try:
        return auth_headers()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def request_port(project, service, pool='web'):
    """Request a port for a project/service."""
    try:
        resp = requests.get(f'{API_URL}/request', params={
            'project': project,
            'service': service,
            'pool': pool,
        }, headers=_headers_or_exit(), timeout=2)
        data = resp.json()

        if 'error' in data:
            print(f"Error: {data['error']}", file=sys.stderr)
            sys.exit(1)

        print(data['port'])
        return data['port']
    except requests.ConnectionError:
        print("Error: Port Authority daemon not running. Start it with: port-authority-daemon", file=sys.stderr)
        sys.exit(1)


def release_port(project, service):
    """Release a port."""
    try:
        resp = requests.get(f'{API_URL}/release', params={
            'project': project,
            'service': service,
        }, headers=_headers_or_exit(), timeout=2)
        data = resp.json()

        if data.get('success'):
            print(f"Released {project}:{service}")
        else:
            print(f"Failed to release {project}:{service}", file=sys.stderr)
            sys.exit(1)
    except requests.ConnectionError:
        print("Error: Port Authority daemon not running", file=sys.stderr)
        sys.exit(1)


def show_status(project=None):
    """Show allocation status."""
    try:
        params = {'project': project} if project else {}
        resp = requests.get(f'{API_URL}/status', params=params, headers=_headers_or_exit(), timeout=2)
        data = resp.json()

        if not data:
            print("No allocations")
            return

        print(f"{'Project:Service':<30} {'Port':<8} {'Pool':<12} {'Active':<8}")
        print("-" * 58)
        for key, info in sorted(data.items()):
            active = 'yes' if info.get('active') else 'no'
            print(f"{key:<30} {info['port']:<8} {info['pool']:<12} {active:<8}")
    except requests.ConnectionError:
        print("Error: Port Authority daemon not running", file=sys.stderr)
        sys.exit(1)


def run_gc(force=False):
    """Preview or perform reclamation of long-stale allocations."""
    try:
        resp = requests.get(f'{API_URL}/gc', params={
            'dry_run': 'false' if force else 'true',
        }, headers=_headers_or_exit(), timeout=5)
        data = resp.json()
        released = data['released']

        if not released:
            print("Nothing stale enough to reclaim")
            return

        verb = "Reclaimed" if force else "Would reclaim (run with --force to actually release)"
        print(f"{verb}:")
        for r in released:
            minutes = int(r['free_for_seconds'] // 60)
            print(f"  {r['key']} — port {r['port']}, free for {minutes}m")
    except requests.ConnectionError:
        print("Error: Port Authority daemon not running", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description='Port Authority CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # request command
    req = subparsers.add_parser('request', help='Request a port')
    req.add_argument('project', help='Project name')
    req.add_argument('service', help='Service name')
    req.add_argument('--pool', default='web', help='Port pool (default: web)')

    # release command
    rel = subparsers.add_parser('release', help='Release a port')
    rel.add_argument('project', help='Project name')
    rel.add_argument('service', help='Service name')

    # status command
    st = subparsers.add_parser('status', help='Show allocations')
    st.add_argument('--project', help='Filter by project')

    # gc command
    gc = subparsers.add_parser('gc', help='Reclaim long-stale allocations')
    gc.add_argument('--force', action='store_true', help='Actually release (default previews only)')

    args = parser.parse_args()

    if args.command == 'request':
        request_port(args.project, args.service, args.pool)
    elif args.command == 'release':
        release_port(args.project, args.service)
    elif args.command == 'status':
        show_status(args.project)
    elif args.command == 'gc':
        run_gc(args.force)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
