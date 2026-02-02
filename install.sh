#!/bin/bash
#
# Alice Assistant Installer
# Installs Alice voice assistant for Omarchy/Arch Linux
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() { echo -e "${BLUE}[*]${NC} $1"; }
print_success() { echo -e "${GREEN}[✓]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "${RED}[✗]${NC} $1"; }

# Configuration
INSTALL_DIR="$HOME/alice-assistant"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║       Alice Assistant Installer          ║"
echo "║   Your snarky personal voice assistant   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check if running on Arch/Omarchy
if ! command -v pacman &> /dev/null; then
    print_error "This installer is designed for Arch Linux / Omarchy"
    exit 1
fi

# Check for required commands
print_status "Checking prerequisites..."

if ! command -v ollama &> /dev/null; then
    print_warning "Ollama not found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

if ! command -v piper &> /dev/null; then
    print_warning "Piper TTS not found. Please install: yay -S piper-tts-bin"
    NEED_PIPER=1
fi

# Install system dependencies
print_status "Installing system dependencies..."
sudo pacman -S --needed --noconfirm \
    python \
    python-pip \
    python-gobject \
    gtk4 \
    tesseract \
    tesseract-data-eng \
    pipewire \
    pipewire-pulse \
    2>/dev/null || true

# Install AUR packages if yay is available
if command -v yay &> /dev/null; then
    print_status "Installing AUR packages..."
    yay -S --needed --noconfirm piper-tts-bin 2>/dev/null || true
fi

# Copy project files
print_status "Installing Alice to $INSTALL_DIR..."

if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

# Create Python virtual environment (need Python 3.13 or older - 3.14 has compatibility issues)
print_status "Setting up Python environment..."
if command -v python3.13 &> /dev/null; then
    python3.13 -m venv venv
elif command -v python3.12 &> /dev/null; then
    python3.12 -m venv venv
elif command -v python3.11 &> /dev/null; then
    python3.11 -m venv venv
else
    print_warning "Python 3.13/3.12/3.11 not found, trying default python (may have issues)"
    python -m venv venv
fi
source venv/bin/activate

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Download Ollama model
print_status "Downloading AI model (dolphin-phi:2.7b)..."
ollama pull dolphin-phi:2.7b

# Create launcher scripts
print_status "Creating launcher scripts..."
mkdir -p "$HOME/.local/bin"

# Main Alice launcher
cat > "$HOME/.local/bin/alice" << 'EOF'
#!/bin/bash
cd "$HOME/alice-assistant"
source venv/bin/activate
python main.py "$@"
EOF
chmod +x "$HOME/.local/bin/alice"

# Startup greeting
cat > "$HOME/.local/bin/alice-greeting" << 'EOF'
#!/bin/bash
PROJECT_DIR="$HOME/alice-assistant"
sleep 3
if ! pgrep -x ollama >/dev/null; then
    ollama serve &>/dev/null &
    sleep 2
fi
cd "$PROJECT_DIR"
source venv/bin/activate
exec python startup_greeting.py
EOF
chmod +x "$HOME/.local/bin/alice-greeting"

# Setup Hyprland integration (if present)
if [ -d "$HOME/.config/hypr" ]; then
    print_status "Configuring Hyprland integration..."

    # Add to autostart if not already there
    if ! grep -q "alice-greeting" "$HOME/.config/hypr/autostart.conf" 2>/dev/null; then
        echo "" >> "$HOME/.config/hypr/autostart.conf"
        echo "# Alice startup greeting" >> "$HOME/.config/hypr/autostart.conf"
        echo "exec-once = alice-greeting" >> "$HOME/.config/hypr/autostart.conf"
    fi

    # Add keybinding if not already there
    if ! grep -q "Super.*A.*Alice" "$HOME/.config/hypr/bindings.conf" 2>/dev/null; then
        echo "" >> "$HOME/.config/hypr/bindings.conf"
        echo "# Alice voice assistant" >> "$HOME/.config/hypr/bindings.conf"
        echo 'bindd = SUPER, A, Alice, exec, alice' >> "$HOME/.config/hypr/bindings.conf"
    fi

    # Add calcurse window rules
    if ! grep -q "calcurse" "$HOME/.config/hypr/hyprland.conf" 2>/dev/null; then
        echo "" >> "$HOME/.config/hypr/hyprland.conf"
        echo "# Calcurse calendar - larger floating window" >> "$HOME/.config/hypr/hyprland.conf"
        echo "windowrule = float on, match:title calcurse" >> "$HOME/.config/hypr/hyprland.conf"
        echo "windowrule = size 1000 700, match:title calcurse" >> "$HOME/.config/hypr/hyprland.conf"
        echo "windowrule = center on, match:title calcurse" >> "$HOME/.config/hypr/hyprland.conf"
    fi
fi

# Setup Waybar calendar (if present)
if [ -f "$HOME/.config/waybar/config.jsonc" ]; then
    print_status "Note: For calendar integration, manually update waybar config"
    print_status "See README.md for waybar calendar setup instructions"
fi

# Initialize memory directory
mkdir -p "$INSTALL_DIR/memory/docs"

# Create default memory files if they don't exist
[ -f "$INSTALL_DIR/memory/context.json" ] || echo '{"current_project": null, "last_interaction": null, "preferences": {}}' > "$INSTALL_DIR/memory/context.json"
[ -f "$INSTALL_DIR/memory/notes.json" ] || echo '{"notes": []}' > "$INSTALL_DIR/memory/notes.json"
[ -f "$INSTALL_DIR/memory/skills.json" ] || echo '{"learned": []}' > "$INSTALL_DIR/memory/skills.json"

# Initialize calcurse
mkdir -p "$HOME/.local/share/calcurse"
touch "$HOME/.local/share/calcurse/apts"

print_success "Installation complete!"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║            Quick Start                   ║"
echo "╠══════════════════════════════════════════╣"
echo "║  Launch Alice:     Super + A             ║"
echo "║  Or from terminal: alice                 ║"
echo "║                                          ║"
echo "║  Alice will greet you on boot!           ║"
echo "╚══════════════════════════════════════════╝"
echo ""
print_status "Read README.md for full documentation"
echo ""
