#!/usr/bin/env bash
# format
ruff format .

# fix
ruff check . --fix

# fix imports
ruff check . --select I --fix

# unsafe fix
# ruff check . --fix --unsafe-fixes

#
mypy .
