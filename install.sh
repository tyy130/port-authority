#!/bin/bash
set -e

echo "Installing Port Authority..."

# Create directories
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/port-authority
mkdir -p ~/.config/port-authority

# Install Python dependencies
pip install -q --break-system-packages -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt

# Create symlinks for CLI tools
ln -sf "$(pwd)/port_authority/cli.py" ~/.local/bin/port-request
ln -sf "$(pwd)/port_authority/daemon.py" ~/.local/bin/port-authority-daemon
ln -sf "$(pwd)/port_authority/mcp_server.py" ~/.local/bin/port-authority-mcp
ln -sf "$(pwd)/bin/port" ~/.local/bin/port

chmod +x ~/.local/bin/port-request
chmod +x ~/.local/bin/port-authority-daemon
chmod +x ~/.local/bin/port-authority-mcp
chmod +x ~/.local/bin/port

# Create default config if not exists
if [ ! -f ~/.config/port-authority/config.yaml ]; then
    cat > ~/.config/port-authority/config.yaml << 'EOF'
pools:
  web:
    range: [3000, 4000]
    description: "Web services, APIs"
  database:
    range: [5000, 6000]
    description: "Database ports"
  internal:
    range: [8000, 9000]
    description: "Internal services"
  tools:
    range: [9000, 10000]
    description: "Tool services"

default_pool: web

# How long a port can sit allocated-but-unbound before the background
# sweep (and `port gc --force`) reclaim it. A service that's simply not
# started yet won't be touched before this elapses.
stale_after_minutes: 60

# Requesting a port for a known service name (postgres, redis, mysql, ...)
# tries its canonical port first, falling back to pool scanning if taken.
# Uncomment to extend or override the built-in list:
# known_services:
#   postgres: 5432
#   my-internal-tool: 7777
EOF
    echo "✓ Created config at ~/.config/port-authority/config.yaml"
fi

# Setup auto-start (systemd on Linux; launchd guidance on macOS)
if command -v systemctl >/dev/null 2>&1 && systemctl --user status >/dev/null 2>&1; then
    mkdir -p ~/.config/systemd/user
    cat > ~/.config/systemd/user/port-authority.service << EOF
[Unit]
Description=Port Authority Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$HOME/.local/bin/port-authority-daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

    systemctl --user daemon-reload
    systemctl --user enable port-authority.service
    systemctl --user start port-authority.service

    echo "✓ Port Authority installed and started (systemd user service)"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    mkdir -p ~/Library/LaunchAgents
    PLIST=~/Library/LaunchAgents/com.portauthority.daemon.plist
    cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.portauthority.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$HOME/.local/bin/port-authority-daemon</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/.local/share/port-authority/daemon.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.local/share/port-authority/daemon.err.log</string>
</dict>
</plist>
EOF

    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"

    echo "✓ Port Authority installed and started (launchd agent)"
    echo "  Logs: ~/.local/share/port-authority/daemon.log"
else
    echo "✓ Port Authority CLI installed"
    echo ""
    echo "⚠️  No systemd user session detected — start the daemon manually:"
    echo "  port-authority-daemon &"
fi

echo ""
echo "The daemon generates an auth token on first start at"
echo "  ~/.config/port-authority/token"
echo "The CLI and Python library read it automatically — nothing to configure."
echo ""
echo "Quick test:"
echo "  port myproject myservice"
echo ""
echo "View status:"
echo "  port status"
echo ""
echo "Want any MCP-compatible agent (not just Claude Code) to call this as a"
echo "native tool? It's an optional dependency, not installed by default:"
echo "  pip install -r requirements-mcp.txt"
echo "  # then register port-authority-mcp with your client — see README.md"
