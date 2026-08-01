#!/usr/bin/env python3
"""Port Authority CLI - Command-line interface for port requests."""

import json
import requests
import sys
import argparse
from pathlib import Path

API_URL = 'http://127.0.0.1:8888'


def request_port(project, service, pool='web'):
    """Request a port for a project/service."""
    try:
        resp = requests.get(f'{API_URL}/request', params={
            'project': project,
            'service': service,
            'pool': pool,
        }, timeout=2)
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
        }, timeout=2)
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
        resp = requests.get(f'{API_URL}/status', params=params, timeout=2)
        data = resp.json()

        if not data:
            print("No allocations")
            return

        print(f"{'Project:Service':<30} {'Port':<8} {'Pool':<12}")
        print("-" * 50)
        for key, info in sorted(data.items()):
            print(f"{key:<30} {info['port']:<8} {info['pool']:<12}")
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

    args = parser.parse_args()

    if args.command == 'request':
        request_port(args.project, args.service, args.pool)
    elif args.command == 'release':
        release_port(args.project, args.service)
    elif args.command == 'status':
        show_status(args.project)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
