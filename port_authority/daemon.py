#!/usr/bin/env python3
"""Port Authority Daemon - Centralized port allocation service."""

import hmac
import json
import re
import secrets
import socket
import sys
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import yaml
import logging

# Allow running this file directly (e.g. symlinked into ~/.local/bin) without
# the package being pip-installed: put the repo root on sys.path so the
# sibling "port_authority" package resolves.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from port_authority._config import TOKEN_FILE

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATE_DIR = Path.home() / '.local/share/port-authority'
STATE_FILE = STATE_DIR / 'allocations.json'
CONFIG_FILE = Path.home() / '.config/port-authority/config.yaml'

STATE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_STALE_AFTER_MINUTES = 60
GC_SWEEP_INTERVAL_SECONDS = 60

# Canonical default ports for common dev services. Requesting a port for a
# service whose name (or alias) matches one of these tries that exact port
# first -- so `port myproject postgres` gets 5432 if it's free, instead of
# an arbitrary port from whatever pool happened to be scanned. Falls back to
# normal pool-range allocation if the canonical port is unavailable, so this
# never turns into a hard requirement. Extend or override via config.yaml's
# `known_services` key -- see README.
DEFAULT_KNOWN_SERVICES = {
    'postgres': 5432, 'postgresql': 5432, 'pg': 5432,
    'mysql': 3306, 'mariadb': 3306,
    'mongodb': 27017, 'mongo': 27017,
    'redis': 6379,
    'memcached': 11211,
    'rabbitmq': 5672,
    'elasticsearch': 9200, 'es': 9200,
    'kafka': 9092,
    'cassandra': 9042,
    'influxdb': 8086,
    'neo4j': 7474,
    'etcd': 2379,
    'consul': 8500,
    'zookeeper': 2181,
    'sqlserver': 1433, 'mssql': 1433,
    'clickhouse': 8123,
}

# project/service names become "project:service" registry keys and get
# interpolated into shell commands by callers, so keep them restrictive.
NAME_RE = re.compile(r'^[A-Za-z0-9_-]+$')


def is_port_free(port, host='127.0.0.1'):
    """Check whether a port is actually bindable on the host right now.

    The registry only tracks ports *this* daemon has handed out — it has no
    idea about services started some other way (docker run -p, a stray
    postgres, etc.). Without this check, request_port() would happily
    return a port something else already owns.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def load_or_create_token():
    """The daemon is the sole issuer of the auth token; clients only read it."""
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    token = secrets.token_hex(24)
    TOKEN_FILE.write_text(token)
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass  # best-effort on platforms without POSIX permissions
    return token


class PortAuthority:
    """Manages port allocations."""

    def __init__(self):
        self.allocations = {}
        self.pools = {}
        self.stale_after_minutes = DEFAULT_STALE_AFTER_MINUTES
        self.known_services = dict(DEFAULT_KNOWN_SERVICES)
        self.lock = threading.Lock()
        self.load_config()
        self.load_state()

    def load_config(self):
        """Load configuration from YAML."""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config = yaml.safe_load(f) or {}
                self.pools = config.get('pools', self._default_pools())
                self.stale_after_minutes = config.get('stale_after_minutes', DEFAULT_STALE_AFTER_MINUTES)
                self.known_services = {
                    **DEFAULT_KNOWN_SERVICES,
                    **(config.get('known_services') or {}),
                }
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
        if not (project and service and NAME_RE.match(project) and NAME_RE.match(service)):
            return {'error': 'project/service must be non-empty and match [A-Za-z0-9_-]+'}

        with self.lock:
            key = f"{project}:{service}"

            # Already allocated? The registry is the source of truth for
            # *ownership* — trust it unconditionally. Re-checking is_port_free
            # here would be wrong: a healthy, currently-running service IS
            # bound to its port, so is_port_free() correctly returns False
            # for the normal steady state. Treating that as "stolen" would
            # yank the allocation out from under every running service on
            # every idempotent lookup. Reclaiming genuinely abandoned
            # allocations is sweep_stale()'s job, not this one's.
            if key in self.allocations:
                return self.allocations[key]['port']

            # Get pool range
            pool_cfg = self.pools.get(pool)
            if not pool_cfg or 'range' not in pool_cfg:
                return {'error': f'Unknown pool: {pool}'}

            try:
                start, end = pool_cfg['range']
            except (ValueError, TypeError):
                return {'error': f'Invalid range config for pool {pool}'}

            # Known service (postgres, redis, ...)? Try its canonical port
            # before falling back to pool scanning -- checked against every
            # allocation regardless of pool, since these ports are usually
            # outside the requested pool's range entirely.
            known_port = self.known_services.get(service.lower())
            if known_port is not None:
                all_allocated = {v['port'] for v in self.allocations.values()}
                if known_port not in all_allocated and is_port_free(known_port):
                    self.allocations[key] = {
                        'port': known_port,
                        'project': project,
                        'service': service,
                        'pool': pool,
                        'allocated_at': time.time(),
                    }
                    self.save_state()
                    logger.info(f"Allocated known-service port {known_port} to {project}:{service}")
                    return known_port

            allocated_ports = {v['port'] for v in self.allocations.values() if v['pool'] == pool}

            # Find first port that's both unclaimed in our registry AND
            # actually bindable on the machine right now.
            for port in range(start, end + 1):
                if port in allocated_ports:
                    continue
                if not is_port_free(port):
                    continue
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
        """Get allocation status, annotated with a live (not persisted)
        'active' flag showing whether something is currently bound to the
        port right now."""
        items = self.allocations.items()
        if project:
            items = [(k, v) for k, v in items if k.startswith(f"{project}:")]
        return {k: {**v, 'active': not is_port_free(v['port'])} for k, v in items}

    def sweep_stale(self, dry_run=True, now=None):
        """Reclaim allocations whose port has been continuously free for
        longer than stale_after_minutes.

        A port being free *right now* proves nothing on its own — the owning
        service may just not have started yet. So this tracks how long each
        allocation has been continuously free (free_since) and only reclaims
        once that exceeds the configured grace period.

        dry_run=True (the default, used by manual `port gc`) never mutates
        state — it only reports what the *next* real sweep would do based on
        free_since values a prior non-dry-run sweep already recorded.
        dry_run=False (used by the background sweep thread, and `port gc
        --force`) updates free_since bookkeeping and actually reclaims.
        """
        now = now if now is not None else time.time()
        threshold = self.stale_after_minutes * 60
        released = []
        changed = False

        with self.lock:
            for key, info in list(self.allocations.items()):
                port = info['port']
                free = is_port_free(port)
                free_since = info.get('free_since')

                if free:
                    if free_since is None:
                        if not dry_run:
                            info['free_since'] = now
                            changed = True
                    elif now - free_since >= threshold:
                        released.append({
                            'key': key,
                            'port': port,
                            'free_for_seconds': now - free_since,
                        })
                        if not dry_run:
                            del self.allocations[key]
                            changed = True
                            logger.info(
                                f"GC: reclaimed {key} (port {port}, "
                                f"free for {int(now - free_since)}s)"
                            )
                elif free_since is not None and not dry_run:
                    info.pop('free_since', None)
                    changed = True

            if changed:
                self.save_state()

        return released


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Port Authority API."""

    authority = None
    token = None

    def _extract_token(self, params):
        auth = self.headers.get('Authorization', '')
        if auth.lower().startswith('bearer '):
            return auth[7:].strip()
        return params.get('token', [None])[0]

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        provided = self._extract_token(params)
        if not (provided and hmac.compare_digest(provided, self.token)):
            self.send_json({'error': 'unauthorized'}, status=401)
            return

        if parsed.path == '/request':
            project = params.get('project', [None])[0]
            service = params.get('service', [None])[0]
            pool = params.get('pool', ['web'])[0]

            if not project or not service:
                self.send_error(400, 'Missing project or service')
                return

            result = self.authority.request_port(project, service, pool)
            self.send_json(result if isinstance(result, dict) else {'port': result})

        elif parsed.path == '/release':
            project = params.get('project', [None])[0]
            service = params.get('service', [None])[0]

            if not project or not service:
                self.send_error(400, 'Missing project or service')
                return

            success = self.authority.release_port(project, service)
            self.send_json({'success': success})

        elif parsed.path == '/status':
            project = params.get('project', [None])[0]
            status = self.authority.get_status(project)
            self.send_json(status)

        elif parsed.path == '/gc':
            dry_run = params.get('dry_run', ['true'])[0].lower() != 'false'
            released = self.authority.sweep_stale(dry_run=dry_run)
            self.send_json({'dry_run': dry_run, 'released': released})

        else:
            self.send_error(404)

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def run_daemon(host='127.0.0.1', port=8888, sweep_interval=GC_SWEEP_INTERVAL_SECONDS):
    """Run the Port Authority daemon."""
    authority = PortAuthority()
    RequestHandler.authority = authority
    RequestHandler.token = load_or_create_token()

    def sweep_loop():
        while True:
            time.sleep(sweep_interval)
            try:
                authority.sweep_stale(dry_run=False)
            except Exception:
                logger.exception("Stale-allocation sweep failed")

    threading.Thread(target=sweep_loop, daemon=True).start()

    server = HTTPServer((host, port), RequestHandler)
    logger.info(f"Port Authority daemon running on {host}:{port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Daemon shutting down")
        server.shutdown()


if __name__ == '__main__':
    run_daemon()
