#!/usr/bin/env bash
# Run test coverage with terminal output
pytest --cov=glovebox

# Generate HTML report
pytest --cov=glovebox --cov-report=html

echo "HTML coverage report generated in htmlcov/index.html"

# Generate XML report for CI tools
# pytest --cov=glovebox --cov-report=xml