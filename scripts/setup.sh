#!/usr/bin/env bash
# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  uv venv
  echo "Activate with: source .venv/bin/activate"
fi

# Install project in development mode with all dependencies
echo "Installing project with development dependencies..."
uv pip install -e ".[dev]"

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
pre-commit install

echo "Setup complete! Activate the virtual environment with: source .venv/bin/activate"