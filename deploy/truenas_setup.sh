#!/bin/bash
# TrueNAS SCALE setup script for the exercise tracking app.
# Run this once from the TrueNAS Shell (System > Shell in the WebUI).
# The app will be installed to /mnt/data/exercise and run as a persistent service.

set -e

APP_DIR="/mnt/data/exercise"
REPO_URL="https://github.com/ahorn885/exercise.git"
BRANCH="main"
SERVICE_FILE="/etc/systemd/system/exercise-app.service"
VENV="$APP_DIR/.venv"

echo "=== Exercise App — TrueNAS SCALE Setup ==="

# 1. Install git if missing
if ! command -v git &>/dev/null; then
    echo "[1/6] Installing git..."
    apt-get install -y git
else
    echo "[1/6] git already installed"
fi

# 2. Clone or update repo
if [ -d "$APP_DIR/.git" ]; then
    echo "[2/6] Updating existing repo..."
    git -C "$APP_DIR" pull origin "$BRANCH"
else
    echo "[2/6] Cloning repo..."
    git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

# 3. Create Python virtualenv
if ! command -v python3 &>/dev/null; then
    echo "[3/6] Installing python3..."
    apt-get install -y python3 python3-venv python3-pip
else
    echo "[3/6] python3 found: $(python3 --version)"
fi

if [ ! -d "$VENV" ]; then
    echo "[3/6] Creating virtualenv..."
    python3 -m venv "$VENV"
fi

echo "[3/6] Installing Python dependencies..."
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
"$VENV/bin/pip" install --quiet gunicorn

# 4. Create instance directory (where SQLite DB lives)
mkdir -p "$APP_DIR/instance"

# 5. Write systemd service
echo "[4/6] Writing systemd service..."
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Exercise Training App
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
Environment=SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
ExecStart=$VENV/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 6. Enable and start
echo "[5/6] Enabling and starting service..."
systemctl daemon-reload
systemctl enable exercise-app
systemctl restart exercise-app

echo ""
echo "=== Setup complete ==="
echo "App is running at: http://$(hostname -I | awk '{print $1}'):5000"
echo "Via Tailscale at:  http://$(tailscale ip -4 2>/dev/null || echo '<tailscale-ip>'):5000"
echo ""
echo "Check status:  systemctl status exercise-app"
echo "View logs:     journalctl -u exercise-app -f"
echo ""
echo "Next: open the app in your browser and go to"
echo "  Garmin > Auth Settings  to log in to Garmin Connect."
