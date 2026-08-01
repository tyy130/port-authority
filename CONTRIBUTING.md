# Contributing

Small tool, low ceremony.

## Setup

```bash
git clone https://github.com/tyy130/port-authority.git
cd port-authority
pip install -r requirements-dev.txt
```

## Running tests

```bash
pytest tests/ -v
```

`tests/test_daemon.py` exercises `PortAuthority` directly (no HTTP server) by pointing `STATE_FILE`/`CONFIG_FILE` at a temp directory per test. `tests/test_http_auth.py` spins up a real `HTTPServer` on an OS-assigned port to check the auth layer end-to-end — logic-only tests can't catch a broken or missing auth check, since `RequestHandler` is what enforces it, not `PortAuthority`.

## Before opening a PR

- `pytest tests/` passes
- New behavior has a test, especially anything touching allocation, auth, or GC logic — that's the part that has to be correct or the whole tool is pointless
- README / INTEGRATION.md updated if you changed CLI syntax or output format

## Reporting issues

Open a GitHub issue with your OS, Python version, and (if relevant) your `~/.config/port-authority/config.yaml`.
