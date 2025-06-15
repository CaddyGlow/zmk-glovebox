#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/libutils.sh"

: "${LOG_LEVEL}=1" # Default to INFO level
: "${WORKSPACE_DIR:=/workspace}"

# Set desired umask
: "${UMASK:=0022}"
umask "$UMASK"

# Cleanup function
cleanup() {
  log_info "CLEANUP: Running cleanup ..."
  if [ -n "${UID:-}" ] && [ -n "${GID:-}" ]; then
    log_info "CLEANUP: Attempting chown $UID:$GID ${WORKSPACE_DIR}"
    chown -R "$UID:$GID" ${WORKSPACE_DIR} || log_warn "CLEANUP: chown failed"
  fi
}

# Handle Docker signals properly
trap 'log_info "TRAP: EXIT"; cleanup' EXIT
trap 'log_warn "TRAP: INT (Ctrl+C)"; cleanup; exit 130' INT
trap 'log_warn "TRAP: TERM (Docker stop)"; cleanup; exit 143' TERM

# Handle UID/GID mapping
if [ -n "${UID:-}" ] && [ -n "${GID:-}" ]; then
  log_info "Using UID:GID $UID:$GID"
fi

log_debug "Setting up signal traps..."
log_debug "Running command: $*"

# Execute the command and wait for it
"$@" &
child_pid=$!
wait $child_pid
exit_code=$?

log_debug "Command completed with exit code: $exit_code"
exit $exit_code
