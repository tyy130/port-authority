#!/usr/bin/env python3
"""Port Authority Daemon - Centralized port allocation service."""

import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import yaml
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATE_DIR = Path.home() / '.local/share/port-authority'
STATE_FILE = STATE_DIR / 'allocations.json'
CONFIG_FILE = Path.home() / '.config/port-authority/config.yaml'
SOCKET_PATH = Path.home() / '.local/run/port-authority.sock'

STATE_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)


class PortAuthority:
    """Manages port allocations."""

    def __init__(self):
        self.allocations = {}
        self.pools = {}
        self.lock = threading.Lock()
        self.load_config()
        self.load_state()

    def load_config(self):
        """Load configuration from YAML."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = yaml.safe_load(f) or {}
                self.pools = config.get('pools', self._default_pools())
        else:
            self.pools = self._default_pools()

    def _default_pools(self):
        """Default pool configuration."""
        return {
            'web': {'range': [3000, 4000], 'description': 'Web services'},
            'api': {'range': [5000, 6000], 'description': 'API services'},
            'internal': {'range': [8000, 9000], 'description': 'Internal services'},
        }

    def load_state(self):
        """Load allocations from disk."""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                self.allocations = json.load(f)

    def save_state(self):
        """Save allocations to disk."""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.allocations, f, indent=2)

    def request_port(self, project, service, pool='web'):
        """Request a port for a project/service."""
        with self.lock:
            key = f"{project}:{service}"

            # Already allocated?
            if key in self.allocations:
                return self.allocations[key]['port']

            # Get pool range
            if pool not in self.pools:
                return {'error': f'Unknown pool: {pool}'}

            start, end = self.pools[pool]['range']
            allocated_ports = {v['port'] for v in self.allocations.values() if v['pool'] == pool}

            # Find first available
            for port in range(start, end + 1):
                if port not in allocated_ports:
                    self.allocations[key] = {
                        'port': port,
                        'project': project,
                        'service': service,
                        'pool': pool,
                        'allocated_at': time.time(),
                    }
                    self.save_state()
                    logger.info(f"Allocated port {port} to {project}:{service}")
                    return port

            return {'error': f'No available ports in pool {pool}'}

    def release_port(self, project, service):
        """Release a port."""
        with self.lock:
            key = f"{project}:{service}"
            if key in self.allocations:
                port = self.allocations[key]['port']
                del self.allocations[key]
                self.save_state()
                logger.info(f"Released port {port} from {project}:{service}")
                return True
            return False

    def get_status(self, project=None):
        """Get allocation status."""
        if project:
            return {k: v for k, v in self.allocations.items() if k.startswith(f"{project}:")}
        return self.allocations


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Port Authority API."""

    authority = None

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)

        if parsed.path == '/request':
            params = parse_qs(parsed.query)
            project = params.get('project', [None])[0]
            service = params.get('service', [None])[0]
            pool = params.get('pool', ['web'])[0]

            if not project or not service:
                self.send_error(400, 'Missing project or service')
                return

            result = self.authority.request_port(project, service, pool)
            self.send_json(result if isinstance(result, dict) else {'port': result})

        elif parsed.path == '/release':
            params = parse_qs(parsed.query)
            project = params.get('project', [None])[0]
            service = params.get('service', [None])[0]

            if not project or not service:
                self.send_error(400, 'Missing project or service')
                return

            success = self.authority.release_port(project, service)
            self.send_json({'success': success})

        elif parsed.path == '/status':
            params = parse_qs(parsed.query)
            project = params.get('project', [None])[0]
            status = self.authority.get_status(project)
            self.send_json(status)

        else:
            self.send_error(404)

    def send_json(self, data):
        """Send JSON response."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_daemon(host='127.0.0.1', port=8888):
    """Run the Port Authority daemon."""
    authority = PortAuthority()
    RequestHandler.authority = authority

    server = HTTPServer((host, port), RequestHandler)
    logger.info(f"Port Authority daemon running on {host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Daemon shutting down")
        server.shutdown()


if __name__ == '__main__':
    run_daemon()
