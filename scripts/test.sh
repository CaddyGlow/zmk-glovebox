#!/usr/bin/env bash
# Run all tests
pytest

# Run only non-integration tests
# pytest -m "not integration"