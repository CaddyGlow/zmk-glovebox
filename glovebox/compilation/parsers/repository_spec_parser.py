"""Repository specification parser for repo@branch syntax."""

import logging
import re

from glovebox.models.base import GloveboxBaseModel


class RepositorySpec(GloveboxBaseModel):
    """Represents a parsed repository specification.

    Attributes:
        repository: Full repository name (e.g., 'moergo-sc/zmk')
        organization: Organization or user name (e.g., 'moergo-sc')
        repo_name: Repository name (e.g., 'zmk')
        branch: Branch name (e.g., 'main', 'v26.01')
        original_spec: Original specification string as provided
    """

    repository: str
    organization: str
    repo_name: str
    branch: str
    original_spec: str

    @property
    def github_url(self) -> str:
        """Generate GitHub URL for this repository.

        Returns:
            GitHub URL string
        """
        return f"https://github.com/{self.repository}"

    @property
    def clone_url(self) -> str:
        """Generate clone URL for this repository.

        Returns:
            Git clone URL string
        """
        return f"https://github.com/{self.repository}.git"

    @property
    def display_name(self) -> str:
        """Generate display name for this repository specification.

        Returns:
            Display name string (repo@branch format)
        """
        return f"{self.repository}@{self.branch}"


class RepositorySpecParser:
    """Parser for repository specifications in repo@branch format.

    Supports formats like:
    - moergo-sc/zmk@main
    - zmkfirmware/zmk@v26.01
    - organization/repository@feature/branch-name
    """

    # Pattern for repository specification: org/repo@branch
    REPO_SPEC_PATTERN = re.compile(
        r"^(?P<organization>[a-zA-Z0-9](?:[-a-zA-Z0-9]*[a-zA-Z0-9])?)/"
        r"(?P<repo_name>[a-zA-Z0-9_.-]+)"
        r"@(?P<branch>.+)$"
    )

    # Pattern for organization/user names (GitHub rules)
    ORG_PATTERN = re.compile(r"^[a-zA-Z0-9](?:[-a-zA-Z0-9]*[a-zA-Z0-9])?$")

    # Pattern for repository names (GitHub rules)
    REPO_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

    def __init__(self) -> None:
        """Initialize the repository specification parser."""
        self.logger = logging.getLogger(__name__)

    def parse(self, spec: str) -> RepositorySpec:
        """Parse a repository specification string.

        Args:
            spec: Repository specification in format 'org/repo@branch'

        Returns:
            RepositorySpec object with parsed components

        Raises:
            ValueError: If specification format is invalid
        """
        try:
            spec = spec.strip()
            if not spec:
                raise ValueError("Repository specification cannot be empty")

            # Check for @ symbol
            if "@" not in spec:
                raise ValueError(
                    "Repository specification must include branch after '@' symbol. "
                    f"Expected format: 'org/repo@branch', got: '{spec}'"
                )

            # Parse with regex
            match = self.REPO_SPEC_PATTERN.match(spec)
            if not match:
                raise ValueError(
                    f"Invalid repository specification format. "
                    f"Expected format: 'org/repo@branch', got: '{spec}'"
                )

            organization = match.group("organization")
            repo_name = match.group("repo_name")
            branch = match.group("branch")

            # Validate components
            self._validate_organization(organization)
            self._validate_repo_name(repo_name)
            self._validate_branch(branch)

            repository = f"{organization}/{repo_name}"

            return RepositorySpec(
                repository=repository,
                organization=organization,
                repo_name=repo_name,
                branch=branch,
                original_spec=spec,
            )

        except Exception as e:
            exc_info = self.logger.isEnabledFor(logging.DEBUG)
            self.logger.error(
                "Failed to parse repository specification '%s': %s",
                spec,
                e,
                exc_info=exc_info,
            )
            raise

    def validate(self, spec: str) -> bool:
        """Validate a repository specification string.

        Args:
            spec: Repository specification to validate

        Returns:
            True if specification is valid, False otherwise
        """
        try:
            self.parse(spec)
            return True
        except (ValueError, Exception):
            return False

    def _validate_organization(self, organization: str) -> None:
        """Validate organization/user name.

        Args:
            organization: Organization name to validate

        Raises:
            ValueError: If organization name is invalid
        """
        if not organization:
            raise ValueError("Organization name cannot be empty")

        if len(organization) > 39:  # GitHub limit
            raise ValueError(
                f"Organization name too long (max 39 characters): '{organization}'"
            )

        if not self.ORG_PATTERN.match(organization):
            raise ValueError(
                f"Invalid organization name '{organization}'. "
                "Must contain only alphanumeric characters and hyphens, "
                "and cannot start or end with a hyphen."
            )

    def _validate_repo_name(self, repo_name: str) -> None:
        """Validate repository name.

        Args:
            repo_name: Repository name to validate

        Raises:
            ValueError: If repository name is invalid
        """
        if not repo_name:
            raise ValueError("Repository name cannot be empty")

        if len(repo_name) > 100:  # GitHub limit
            raise ValueError(
                f"Repository name too long (max 100 characters): '{repo_name}'"
            )

        if not self.REPO_NAME_PATTERN.match(repo_name):
            raise ValueError(
                f"Invalid repository name '{repo_name}'. "
                "Must contain only alphanumeric characters, hyphens, underscores, and periods."
            )

        # Check for reserved names
        reserved_names = {".git", "..", "."}
        if repo_name.lower() in reserved_names:
            raise ValueError(f"Repository name '{repo_name}' is reserved")

    def _validate_branch(self, branch: str) -> None:
        """Validate branch name.

        Args:
            branch: Branch name to validate

        Raises:
            ValueError: If branch name is invalid
        """
        if not branch:
            raise ValueError("Branch name cannot be empty")

        if len(branch) > 250:  # Reasonable limit for branch names
            raise ValueError(f"Branch name too long (max 250 characters): '{branch}'")

        # Git branch name rules (simplified)
        invalid_chars = {" ", "~", "^", ":", "?", "*", "[", "\\", "\x7f"}
        if any(char in branch for char in invalid_chars):
            raise ValueError(
                f"Branch name '{branch}' contains invalid characters. "
                "Branch names cannot contain spaces, ~, ^, :, ?, *, [, \\, or control characters."
            )

        # Cannot start/end with certain characters
        if branch.startswith((".", "/", "-")) or branch.endswith((".", "/", ".lock")):
            raise ValueError(
                f"Branch name '{branch}' has invalid format. "
                "Branch names cannot start with '.', '/', '-' or end with '.', '/', '.lock'."
            )

        # Cannot contain consecutive dots or slashes
        if ".." in branch or "//" in branch:
            raise ValueError(
                f"Branch name '{branch}' cannot contain consecutive dots '..' or slashes '//'."
            )


def create_repository_spec_parser() -> RepositorySpecParser:
    """Create a repository specification parser instance.

    Returns:
        Configured RepositorySpecParser instance
    """
    return RepositorySpecParser()
