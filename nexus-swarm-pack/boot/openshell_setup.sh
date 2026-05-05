#!/usr/bin/env bash
# NEXUS Swarm Pack - OpenShell Setup Script
# Supports 3 deployment modes: rootless, remote, standalone

set -euo pipefail

MODE="${1:-rootless}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 NEXUS OpenShell Setup - Mode: $MODE"
echo "=" | awk '{for(i=1;i<=60;i++)printf $0}'
echo

install_podman_static() {
    echo "📦 Installing Podman (static binary)..."
    mkdir -p ~/.local/bin
    
    if command -v podman &>/dev/null; then
        echo "✓ Podman already installed"
        return 0
    fi
    
    # Download static Podman binary
    curl -fsSL https://github.com/mgoltzsche/podman-static/releases/latest/download/podman-linux-amd64.tar.gz \
        | tar xz -C ~/.local/bin
    
    export PATH="$HOME/.local/bin/podman-linux-amd64/usr/local/bin:$HOME/.local/bin:$PATH"
    echo "✓ Podman installed to ~/.local/bin"
}

configure_containers() {
    echo "⚙️  Configuring containers.conf..."
    mkdir -p ~/.config/containers
    
    cat > ~/.config/containers/containers.conf <<'EOF'
[network]
default_rootless_network_cmd = "pasta"
[storage]
driver = "overlay"
EOF
    echo "✓ Containers configuration created"
}

start_podman_service() {
    echo "🔌 Starting Podman system service..."
    export XDG_RUNTIME_DIR="$HOME/.local/run"
    mkdir -p "$XDG_RUNTIME_DIR"
    
    if pgrep -f "podman system service" &>/dev/null; then
        echo "✓ Podman service already running"
        return 0
    fi
    
    podman system service --time=0 &
    sleep 2
    echo "✓ Podman service started"
}

install_openshell_cli() {
    echo "🐚 Installing OpenShell CLI..."
    
    if command -v openshell &>/dev/null; then
        echo "✓ OpenShell CLI already installed"
        return 0
    fi
    
    curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh
    echo "✓ OpenShell CLI installed"
}

setup_rootless_mode() {
    echo "📋 Checking prerequisites for rootless mode..."
    
    # Check subuid/subgid
    if ! grep -q "^$(whoami):" /etc/subuid 2>/dev/null; then
        echo "❌ ERROR: subuid not configured for user $(whoami)"
        echo ""
        echo "Sysadmin must run:"
        echo "  echo $(whoami):100000:65536 >> /etc/subuid"
        echo "  echo $(whoami):100000:65536 >> /etc/subgid"
        echo "  apt install -y uidmap"
        echo "  usermod -a -G fuse $(whoami)"
        echo ""
        exit 1
    fi
    
    # Check newuidmap
    if ! command -v newuidmap &>/dev/null; then
        echo "❌ ERROR: newuidmap not found in PATH"
        echo "Sysadmin must run: apt install -y uidmap"
        exit 1
    fi
    
    echo "✓ Prerequisites verified"
    
    install_podman_static
    configure_containers
    start_podman_service
    install_openshell_cli
    
    echo ""
    echo "✅ Rootless mode setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. openshell doctor check"
    echo "  2. openshell gateway start"
    echo "  3. python boot/nexus_boot.py"
}

setup_remote_mode() {
    echo "🌐 Remote Gateway Mode"
    echo ""
    echo "This mode connects to a remote OpenShell gateway."
    echo ""
    echo "On your REMOTE host (with Docker access), run:"
    echo "  curl -LsSf https://raw.githubusercontent.com/NVIDIA/OpenShell/main/install.sh | sh"
    echo "  openshell gateway start"
    echo ""
    echo "Then on THIS machine, run:"
    echo "  openshell gateway add ssh://user@remote-host:8080"
    echo "  openshell status"
    echo ""
    echo "After connecting, run: python boot/nexus_boot.py"
}

setup_standalone_mode() {
    echo "📦 Standalone Binary Mode"
    echo ""
    echo "Downloading standalone openshell-gateway binary..."
    
    ARCH=$(uname -m)
    OS=$(uname -s)
    
    case "${OS}-${ARCH}" in
        Linux-x86_64)
            ASSET="openshell-gateway-x86_64-unknown-linux-gnu"
            ;;
        Linux-aarch64)
            ASSET="openshell-gateway-aarch64-unknown-linux-gnu"
            ;;
        *)
            echo "❌ Unsupported platform: ${OS}-${ARCH}"
            exit 1
            ;;
    esac
    
    echo "Asset: $ASSET"
    echo ""
    echo "Download from: https://github.com/NVIDIA/OpenShell/releases/latest"
    echo "Extract and run: ./$ASSET --port 8080"
    echo ""
    echo "Then register gateway:"
    echo "  openshell gateway add http://127.0.0.1:8080 --local"
}

case "$MODE" in
    rootless)
        setup_rootless_mode
        ;;
    remote)
        setup_remote_mode
        ;;
    standalone)
        setup_standalone_mode
        ;;
    *)
        echo "Usage: $0 {rootless|remote|standalone}"
        exit 1
        ;;
esac
