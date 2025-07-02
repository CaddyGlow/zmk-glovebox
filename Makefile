.PHONY: test lint format fmt coverage setup clean docs docs-clean docs-serve view-docs build check-package publish publish-test docker-image docker-publish release tag-release help

help:
	@echo "Available commands:"
	@echo "  make test       - Run all tests"
	@echo "  make lint       - Run linting checks"
	@echo "  make format     - Format code and fix linting issues"
	@echo "  make coverage   - Run tests with coverage reporting"
	@echo "  make setup      - Create virtual environment and install dependencies"
	@echo "  make clean      - Clean build artifacts and coverage reports"
	@echo "  make docs       - Build documentation with MkDocs"
	@echo "  make docs-clean - Clean documentation build artifacts"
	@echo "  make docs-serve - Serve documentation with live reload"
	@echo "  make view-docs  - Instructions for viewing documentation"
	@echo "  make build      - Build package for distribution"
	@echo "  make check-package - Check package metadata and readiness"
	@echo "  make publish    - Build and publish package to PyPI"
	@echo "  make publish-test - Build and publish package to TestPyPI"
	@echo "  make docker-image - Build glovebox docker image with version tag"
	@echo "  make docker-publish - Build and publish docker image to registries"
	@echo "  make tag-release - Create and push git tag for release"
	@echo "  make release    - Full release: tag, build, publish to PyPI and Docker"

test:
	uv run scripts/test.sh

lint:
	uv run scripts/lint.sh

format:
	uv run scripts/format.sh
fmt: format

coverage:
	uv run scripts/coverage.sh

setup:
	./scripts/setup.sh

clean:
	rm -rf build/ htmlcov/ .coverage .pytest_cache/ *.egg-info/ dist/ site/

docs:
	uv run mkdocs build

docs-clean:
	rm -rf site/

docs-serve:
	uv run mkdocs serve

view-docs:
	@echo "To view documentation:"
	@echo "1. Run 'make docs' to build"
	@echo "2. Open site/index.html in your browser"
	@echo "Or run 'make docs-serve' for live preview"

build:
	./scripts/build.sh

check-package:
	./scripts/check-package.sh

publish: build
	@echo "Publishing to PyPI..."
	@echo "WARNING: This will publish to the live PyPI repository!"
	@echo "Make sure you want to proceed with this release."
	@read -p "Continue? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	uv publish

publish-test: build
	@echo "Publishing to TestPyPI..."
	uv publish --index-url https://test.pypi.org/legacy/

docker-image:
	$(eval VERSION := $(shell uv run python -c 'import glovebox; print(glovebox.__version__.replace("+", "-").replace("/", "-"))'))
	@echo "Building Glovebox Docker image version $(VERSION)..."
	docker buildx build --platform linux/amd64,linux/arm64 -t glovebox/glovebox:$(VERSION) -t glovebox/glovebox:latest .
	@echo "✓ Docker image built: glovebox/glovebox:$(VERSION)"

docker-publish: docker-image
	$(eval VERSION := $(shell uv run python -c 'import glovebox; print(glovebox.__version__.replace("+", "-").replace("/", "-"))'))
	@echo "Publishing Docker images to registries..."
	@echo "Publishing to Docker Hub..."
	docker push glovebox/glovebox:$(VERSION)
	docker push glovebox/glovebox:latest
	@echo "Publishing to GitHub Container Registry..."
	docker tag glovebox/glovebox:$(VERSION) ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/' | tr '[:upper:]' '[:lower:]')/glovebox:$(VERSION)
	docker tag glovebox/glovebox:latest ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/' | tr '[:upper:]' '[:lower:]')/glovebox:latest
	docker push ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/' | tr '[:upper:]' '[:lower:]')/glovebox:$(VERSION)
	docker push ghcr.io/$(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/' | tr '[:upper:]' '[:lower:]')/glovebox:latest
	@echo "✓ Docker images published successfully"

tag-release:
	$(eval VERSION := $(shell uv run python -c 'import glovebox; print(glovebox.__version__)'))
	@echo "Creating release tag v$(VERSION)..."
	@if git tag -l | grep -q "^v$(VERSION)$$"; then \
		echo "Error: Tag v$(VERSION) already exists"; \
		exit 1; \
	fi
	@echo "Current version: $(VERSION)"
	@read -p "Create and push tag v$(VERSION)? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	git tag -a v$(VERSION) -m "Release version $(VERSION)"
	git push origin v$(VERSION)
	@echo "✓ Tag v$(VERSION) created and pushed"

release: test lint check-package
	$(eval VERSION := $(shell uv run python -c 'import glovebox; print(glovebox.__version__)'))
	@echo "=== Glovebox Release Process v$(VERSION) ==="
	@echo "This will:"
	@echo "  1. Create and push git tag v$(VERSION)"
	@echo "  2. Build and publish Python package to PyPI"
	@echo "  3. Build and publish Docker images"
	@echo ""
	@echo "Prerequisites checked:"
	@echo "  ✓ Tests passed"
	@echo "  ✓ Linting passed" 
	@echo "  ✓ Package metadata validated"
	@echo ""
	@read -p "Proceed with full release? (y/N): " confirm && [ "$$confirm" = "y" ] || exit 1
	$(MAKE) tag-release
	@echo "Waiting for GitHub Actions to complete..."
	@echo "The release workflow will automatically:"
	@echo "  - Build and publish to PyPI"
	@echo "  - Build and publish Docker images"
	@echo "  - Create GitHub release with changelog"
	@echo ""
	@echo "✓ Release process initiated!"
	@echo "Monitor progress at: https://github.com/$(shell git config --get remote.origin.url | sed 's/.*github.com[:/]\([^.]*\).*/\1/')/actions"

# Legacy docker build for ZMK toolchain (kept for compatibility)
docker-zmk-toolchain:
	$(eval VERSION := $(shell uv run python -c 'import glovebox; print(glovebox.__version__.replace("+", "-").replace("/", "-"))'))
	docker buildx build --build-arg BUILDTIME=$(shell date +%s) -t glove80-zmk-config-docker:$(VERSION) -f keyboards/glove80/toolchain/Dockerfile keyboards/glove80/toolchain
