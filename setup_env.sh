#!/bin/bash
set -e

echo "Setting up Python virtual environment in .venv..."
python3 -m venv .venv
source .venv/bin/activate

echo "Installing requirements..."
pip install -r requirements.txt

echo ""
echo "Setup complete!"
echo "To activate the environment, run:"
echo "  source .venv/bin/activate"
