#!/bin/bash
# Alice Assistant Setup Script

set -e

echo "=== Alice Assistant Setup ==="
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install piper-tts
echo "Installing Piper TTS..."
pip install piper-tts

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo ""
    echo "WARNING: Ollama not found. Install it with:"
    echo "  curl -fsSL https://ollama.ai/install.sh | sh"
    echo ""
fi

# Pull the recommended model
echo ""
echo "Pulling recommended LLM model (qwen2.5:3b)..."
if command -v ollama &> /dev/null; then
    ollama pull qwen2.5:3b
fi

# Create memory directory structure
mkdir -p memory/docs

# Initialize empty memory files
if [ ! -f memory/context.json ]; then
    echo '{"current_project": null, "last_interaction": null, "preferences": {}}' > memory/context.json
fi

if [ ! -f memory/notes.json ]; then
    echo '{"notes": []}' > memory/notes.json
fi

if [ ! -f memory/skills.json ]; then
    echo '{"learned": []}' > memory/skills.json
fi

# Make main.py executable
chmod +x main.py

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To run Alice:"
echo "  cd $PROJECT_DIR"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Or create a launcher script in ~/.local/bin/alice"
echo ""
