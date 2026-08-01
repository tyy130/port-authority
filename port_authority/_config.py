"""Paths and helpers shared between the daemon and clients (cli.py, __init__.py)."""
from pathlib import Path

API_URL = 'http://127.0.0.1:8888'
TOKEN_FILE = Path.home() / '.config/port-authority/token'


def load_token():
    """Read the auth token a running daemon already created.

    Only the daemon mints tokens (load_or_create_token in daemon.py) — the
    client side just reads what's there so a stale/mismatched client never
    silently creates a second token that doesn't match the daemon's.
    """
    if not TOKEN_FILE.exists():
        raise Exception(
            "No auth token found at "
            f"{TOKEN_FILE}. Is the daemon running? Start it with: port-authority-daemon"
        )
    return TOKEN_FILE.read_text().strip()


def auth_headers():
    return {'Authorization': f'Bearer {load_token()}'}
