#!/usr/bin/env bash
set -eux

TMPDIR="$HOME/projects/glovebox/tmp"
tmp_sess=""

# Cleanup function with confirmation
cleanup() {
  local exit_code=$?

  if [[ -n "$tmp_sess" && -d "$tmp_sess" ]]; then
    echo
    echo "Temporary directory created: $tmp_sess"

    if [[ $exit_code -ne 0 ]]; then
      echo "Script failed with exit code: $exit_code"
    fi

    read -p "Do you want to delete the temporary directory? [y/N]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
      echo "Removing temporary directory: $tmp_sess"
      rm -rf "$tmp_sess"
      echo "Cleanup completed."
    else
      echo "Temporary directory preserved: $tmp_sess"
    fi
  fi
}

# Set up traps for cleanup
trap cleanup EXIT ERR INT TERM

# Main execution function
main() {
  tmp_sess=$(mktemp -d)
  echo "Created temporary directory: $tmp_sess"

  cd "$tmp_sess"

  # Your main command - this might fail
  glovebox moergo download 0d52f708-aa40-4ea5-b5f6-f9881412bd21

  return 0
}

# Execute main function
main
