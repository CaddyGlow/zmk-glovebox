#!/usr/bin/env bash
# fix
ruff check . --fix

# fix imports
ruff check . --select I --fix

# format
ruff format .
