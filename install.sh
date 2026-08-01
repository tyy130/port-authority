#!/bin/bash
set -e

echo "Installing Port Authority..."

# Create directories
mkdir -p ~/.local/bin
mkdir -p ~/.local/share/port-authority
mkdir -p ~/.local/run
mkdir -p ~/.config/port-authority

# Install Python dependencies
pip install -q --break-system-packages -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt

# Create symlinks for CLI tools
ln -sf "$(pwd)/port_authority/cli.py" ~/.local/bin/port-request
ln -sf "$(pwd)/port_authority/daemon.py" ~/.local/bin/port-authority-daemon
ln -sf "$(pwd)/bin/port" ~/.local/bin/port

chmod +x ~/.local/bin/port-request
chmod +x ~/.local/bin/port-authority-daemon
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
EOF
    echo "✓ Created config at ~/.config/port-authority/config.yaml"
fi

# Setup systemd service
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

echo "✓ Port Authority installed and started"
echo ""
echo "Quick test:"
echo "  port-request myproject myservice"
echo ""
echo "View status:"
echo "  port-request status"
