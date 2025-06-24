#!/usr/bin/env bash
# Open the generated documentation in the default browser

cd "$(dirname "$0")/.."

DOC_FILE="docs/_build/html/index.html"

if [ ! -f "$DOC_FILE" ]; then
  echo "Documentation not found. Building documentation first..."
  make docs
fi

if [ -f "$DOC_FILE" ]; then
  echo "Opening documentation in default browser..."

  # Try to open with different browsers/tools
  if command -v xdg-open >/dev/null; then
    xdg-open "$DOC_FILE"
  elif command -v open >/dev/null; then
    open "$DOC_FILE" # macOS
  elif command -v start >/dev/null; then
    start "$DOC_FILE" # Windows
  else
    echo "Could not open browser automatically."
    echo "Please open file://$PWD/$DOC_FILE in your browser."
  fi
else
  echo "Failed to build documentation."
  exit 1
fi

