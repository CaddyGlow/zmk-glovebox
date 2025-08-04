"""Tests for repository specification parser."""

import pytest

from glovebox.compilation.parsers.repository_spec_parser import (
    RepositorySpec,
    RepositorySpecParser,
    create_repository_spec_parser,
)


pytestmark = [pytest.mark.network, pytest.mark.integration]

pytestmark = pytest.mark.integration


class TestRepositorySpec:
    """Test RepositorySpec model functionality."""

    def test_repository_spec_basic_properties(self):
        """Test basic properties of RepositorySpec."""
        spec = RepositorySpec(
            repository="moergo-sc/zmk",
            organization="moergo-sc",
            repo_name="zmk",
            branch="main",
            original_spec="moergo-sc/zmk@main",
        )

        assert spec.repository == "moergo-sc/zmk"
        assert spec.organization == "moergo-sc"
        assert spec.repo_name == "zmk"
        assert spec.branch == "main"
        assert spec.original_spec == "moergo-sc/zmk@main"

    def test_github_url_property(self):
        """Test GitHub URL generation."""
        spec = RepositorySpec(
            repository="zmkfirmware/zmk",
            organization="zmkfirmware",
            repo_name="zmk",
            branch="v3.5.0",
            original_spec="zmkfirmware/zmk@v3.5.0",
        )

        assert spec.github_url == "https://github.com/zmkfirmware/zmk"

    def test_clone_url_property(self):
        """Test clone URL generation."""
        spec = RepositorySpec(
            repository="moergo-sc/zmk",
            organization="moergo-sc",
            repo_name="zmk",
            branch="v26.01",
            original_spec="moergo-sc/zmk@v26.01",
        )

        assert spec.clone_url == "https://github.com/moergo-sc/zmk.git"

    def test_display_name_property(self):
        """Test display name generation."""
        spec = RepositorySpec(
            repository="test-org/test-repo",
            organization="test-org",
            repo_name="test-repo",
            branch="feature/new-layout",
            original_spec="test-org/test-repo@feature/new-layout",
        )

        assert spec.display_name == "test-org/test-repo@feature/new-layout"


class TestRepositorySpecParser:
    """Test RepositorySpecParser functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.parser = RepositorySpecParser()

    def test_parse_valid_basic_spec(self):
        """Test parsing valid basic repository specification."""
        spec_str = "moergo-sc/zmk@main"
        result = self.parser.parse(spec_str)

        assert result.repository == "moergo-sc/zmk"
        assert result.organization == "moergo-sc"
        assert result.repo_name == "zmk"
        assert result.branch == "main"
        assert result.original_spec == spec_str

    def test_parse_valid_version_branch(self):
        """Test parsing repository specification with version branch."""
        spec_str = "zmkfirmware/zmk@v3.5.0"
        result = self.parser.parse(spec_str)

        assert result.repository == "zmkfirmware/zmk"
        assert result.organization == "zmkfirmware"
        assert result.repo_name == "zmk"
        assert result.branch == "v3.5.0"
        assert result.original_spec == spec_str

    def test_parse_valid_complex_branch(self):
        """Test parsing repository specification with complex branch name."""
        spec_str = "user/repo@feature/new-functionality"
        result = self.parser.parse(spec_str)

        assert result.repository == "user/repo"
        assert result.organization == "user"
        assert result.repo_name == "repo"
        assert result.branch == "feature/new-functionality"
        assert result.original_spec == spec_str

    def test_parse_valid_underscore_repo(self):
        """Test parsing repository with underscores and dots."""
        spec_str = "org/my_repo.test@main"
        result = self.parser.parse(spec_str)

        assert result.repository == "org/my_repo.test"
        assert result.organization == "org"
        assert result.repo_name == "my_repo.test"
        assert result.branch == "main"

    def test_parse_empty_string(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(
            ValueError, match="Repository specification cannot be empty"
        ):
            self.parser.parse("")

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string raises ValueError."""
        with pytest.raises(
            ValueError, match="Repository specification cannot be empty"
        ):
            self.parser.parse("   ")

    def test_parse_missing_at_symbol(self):
        """Test parsing specification without @ symbol raises ValueError."""
        with pytest.raises(ValueError, match="must include branch after '@' symbol"):
            self.parser.parse("moergo-sc/zmk")

    def test_parse_missing_slash(self):
        """Test parsing specification without / symbol raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("moergo-sc@main")

    def test_parse_missing_branch(self):
        """Test parsing specification with empty branch raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("moergo-sc/zmk@")

    def test_parse_missing_repo_name(self):
        """Test parsing specification with empty repo name raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("moergo-sc/@main")

    def test_parse_missing_organization(self):
        """Test parsing specification with empty organization raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("/zmk@main")

    def test_parse_invalid_organization_start_hyphen(self):
        """Test parsing with organization starting with hyphen raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("-moergo/zmk@main")

    def test_parse_invalid_organization_end_hyphen(self):
        """Test parsing with organization ending with hyphen raises ValueError."""
        with pytest.raises(ValueError, match="Invalid repository specification format"):
            self.parser.parse("moergo-/zmk@main")

    def test_parse_invalid_organization_too_long(self):
        """Test parsing with organization name too long raises ValueError."""
        long_org = "a" * 40  # GitHub limit is 39 characters
        with pytest.raises(ValueError, match="Organization name too long"):
            self.parser.parse(f"{long_org}/zmk@main")

    def test_parse_invalid_repo_name_too_long(self):
        """Test parsing with repo name too long raises ValueError."""
        long_repo = "a" * 101  # GitHub limit is 100 characters
        with pytest.raises(ValueError, match="Repository name too long"):
            self.parser.parse(f"org/{long_repo}@main")

    def test_parse_invalid_repo_name_reserved(self):
        """Test parsing with reserved repo name raises ValueError."""
        with pytest.raises(ValueError, match="Repository name '.git' is reserved"):
            self.parser.parse("org/.git@main")

    def test_parse_invalid_branch_with_spaces(self):
        """Test parsing with branch containing spaces raises ValueError."""
        with pytest.raises(
            ValueError, match="Branch name .* contains invalid characters"
        ):
            self.parser.parse("org/repo@feature with spaces")

    def test_parse_invalid_branch_with_control_chars(self):
        """Test parsing with branch containing control characters raises ValueError."""
        with pytest.raises(
            ValueError, match="Branch name .* contains invalid characters"
        ):
            self.parser.parse("org/repo@feature~branch")

    def test_parse_invalid_branch_start_dot(self):
        """Test parsing with branch starting with dot raises ValueError."""
        with pytest.raises(ValueError, match="Branch name .* has invalid format"):
            self.parser.parse("org/repo@.feature")

    def test_parse_invalid_branch_end_lock(self):
        """Test parsing with branch ending with .lock raises ValueError."""
        with pytest.raises(ValueError, match="Branch name .* has invalid format"):
            self.parser.parse("org/repo@feature.lock")

    def test_parse_invalid_branch_consecutive_dots(self):
        """Test parsing with branch containing consecutive dots raises ValueError."""
        with pytest.raises(ValueError, match="cannot contain consecutive dots"):
            self.parser.parse("org/repo@feature..branch")

    def test_parse_invalid_branch_consecutive_slashes(self):
        """Test parsing with branch containing consecutive slashes raises ValueError."""
        with pytest.raises(ValueError, match="cannot contain consecutive .* slashes"):
            self.parser.parse("org/repo@feature//branch")

    def test_parse_invalid_branch_too_long(self):
        """Test parsing with branch name too long raises ValueError."""
        long_branch = "a" * 251  # Limit is 250 characters
        with pytest.raises(ValueError, match="Branch name too long"):
            self.parser.parse(f"org/repo@{long_branch}")

    def test_validate_valid_spec(self):
        """Test validate method returns True for valid specification."""
        assert self.parser.validate("moergo-sc/zmk@main") is True
        assert self.parser.validate("zmkfirmware/zmk@v3.5.0") is True
        assert self.parser.validate("user/repo@feature/branch") is True

    def test_validate_invalid_spec(self):
        """Test validate method returns False for invalid specification."""
        assert self.parser.validate("") is False
        assert self.parser.validate("invalid") is False
        assert self.parser.validate("org/repo") is False
        assert self.parser.validate("org@branch") is False
        assert self.parser.validate("-org/repo@main") is False

    def test_validate_exception_handling(self):
        """Test validate method handles exceptions gracefully."""
        # Test with various problematic inputs
        assert self.parser.validate("org/repo@feature..branch") is False
        assert self.parser.validate("org/repo@.feature") is False
        assert self.parser.validate("-org/repo@main") is False


class TestRepositorySpecParserEdgeCases:
    """Test edge cases and boundary conditions."""

    def setup_method(self):
        """Set up test environment."""
        self.parser = RepositorySpecParser()

    def test_parse_minimum_valid_lengths(self):
        """Test parsing with minimum valid component lengths."""
        # Minimum org (1 char), repo (1 char), branch (1 char)
        # Note: org must have at least 1 alphanumeric char, or 2+ chars if containing hyphens
        spec_str = "a/b@c"
        result = self.parser.parse(spec_str)

        assert result.organization == "a"
        assert result.repo_name == "b"
        assert result.branch == "c"

    def test_parse_maximum_valid_lengths(self):
        """Test parsing with maximum valid component lengths."""
        # Maximum org (39 chars), repo (100 chars), branch (250 chars)
        max_org = "a" * 39
        max_repo = "b" * 100
        max_branch = "c" * 250

        spec_str = f"{max_org}/{max_repo}@{max_branch}"
        result = self.parser.parse(spec_str)

        assert result.organization == max_org
        assert result.repo_name == max_repo
        assert result.branch == max_branch

    def test_parse_special_characters_in_repo(self):
        """Test parsing with special characters allowed in repo names."""
        spec_str = "org/repo-name_with.dots@main"
        result = self.parser.parse(spec_str)

        assert result.repo_name == "repo-name_with.dots"

    def test_parse_complex_branch_names(self):
        """Test parsing various complex but valid branch names."""
        test_cases = [
            "org/repo@release/v1.0.0",
            "org/repo@hotfix/bug-123",
            "org/repo@feature/user-auth",
            "org/repo@develop",
            "org/repo@v26.01-rc1",
            "org/repo@main",
            "org/repo@master",
        ]

        for spec_str in test_cases:
            result = self.parser.parse(spec_str)
            expected_branch = spec_str.split("@")[1]
            assert result.branch == expected_branch

    def test_parse_numeric_organization_and_repo(self):
        """Test parsing with numeric components."""
        spec_str = "user123/repo456@branch789"
        result = self.parser.parse(spec_str)

        assert result.organization == "user123"
        assert result.repo_name == "repo456"
        assert result.branch == "branch789"

    def test_parse_preserves_original_spec(self):
        """Test that original specification is preserved exactly."""
        test_specs = [
            "moergo-sc/zmk@main",
            "zmkfirmware/zmk@v3.5.0",
            "user/my-repo@feature/new-layout",
        ]

        for spec_str in test_specs:
            result = self.parser.parse(spec_str)
            assert result.original_spec == spec_str


class TestCreateRepositorySpecParser:
    """Test factory function for repository specification parser."""

    def test_create_repository_spec_parser(self):
        """Test factory function creates parser instance."""
        parser = create_repository_spec_parser()

        assert isinstance(parser, RepositorySpecParser)
        assert hasattr(parser, "parse")
        assert hasattr(parser, "validate")

    def test_factory_creates_working_parser(self):
        """Test that factory-created parser works correctly."""
        parser = create_repository_spec_parser()

        # Test basic functionality
        result = parser.parse("test/repo@main")
        assert result.repository == "test/repo"
        assert result.branch == "main"

        # Test validation
        assert parser.validate("valid/repo@main") is True
        assert parser.validate("invalid") is False
