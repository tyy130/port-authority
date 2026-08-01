#!/usr/bin/env python3
"""Example: Using Port Authority from Python.

Run from anywhere: `pip install -e /path/to/port-authority` first, or just
run this script directly — it adds the repo root to sys.path either way.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from port_authority import request_port, release_port, get_status

# Request a port
try:
    port = request_port('myproject', 'myservice', pool='web')
    print(f"Allocated port: {port}")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)

# Use the port
print(f"Starting service on port {port}...")
# app.run(port=port)

# Show current status
print("\nCurrent allocations:")
status = get_status()
for key, info in status.items():
    print(f"  {key}: {info['port']} ({info['pool']})")

# Release when done
print(f"\nReleasing port...")
release_port('myproject', 'myservice')
