"""Tests for simplified CLI parameter factory."""

from __future__ import annotations

from typing import Annotated, get_args, get_origin

import pytest
import typer

from glovebox.cli.helpers.parameter_factory import (
    CommonParameterSets,
    ParameterFactory,
)


class TestSimplifiedParameterFactory:
    """Test the new simplified parameter factory methods."""

    def test_create_input_parameter_required(self):
        """Test creating a required input parameter."""
        param = ParameterFactory.create_input_parameter()

        # Verify it returns an Annotated type
        assert get_origin(param) is Annotated
        args = get_args(param)
        assert len(args) == 2

        # Check the type
        type_arg = args[0]
        assert type_arg is str

        # Check the typer.Argument
        argument = args[1]
        assert isinstance(argument, typer.models.ArgumentInfo)
        assert argument.default == ...  # Required parameter uses ellipsis
        assert argument.help == "Input source (file, '-' for stdin, '@name' for library)"
        assert not argument.show_default

    def test_create_input_parameter_optional(self):
        """Test creating an optional input parameter."""
        param = ParameterFactory.create_input_parameter(
            help_text="Custom input help",
            default="default.json",
            required=False
        )

        # Verify the annotation
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]

        assert type_arg == str | None
        # Default is now set in function signature, not in Argument
        assert argument.default == ...  # Typer uses ellipsis for no default in Argument
        assert argument.help == "Custom input help"
        assert argument.show_default is True

    def test_create_input_parameter_json_completion(self):
        """Test JSON files get autocompletion."""
        param = ParameterFactory.create_input_parameter(
            help_text="JSON layout file"
        )

        args = get_args(param)
        argument = args[1]
        assert argument.autocompletion is not None

    def test_create_output_parameter_option(self):
        """Test creating an output option parameter."""
        param = ParameterFactory.create_output_parameter()

        # Verify the annotation
        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg == str | None
        assert isinstance(option, typer.models.OptionInfo)
        assert option.param_decls == ("--output", "-o")
        assert option.help == "Output destination (file, directory, '-' for stdout)"

    def test_create_output_parameter_argument(self):
        """Test creating an output argument parameter."""
        param = ParameterFactory.create_output_parameter(
            help_text="Output file",
            default="out.txt",
            is_option=False
        )

        args = get_args(param)
        type_arg = args[0]
        argument = args[1]

        assert type_arg == str | None
        assert isinstance(argument, typer.models.ArgumentInfo)
        assert argument.default == ...  # Default is in function signature
        assert argument.help == "Output file"
        assert argument.show_default is True

    def test_create_profile_parameter_optional(self):
        """Test creating an optional profile parameter."""
        param = ParameterFactory.create_profile_parameter()

        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg == str | None
        assert isinstance(option, typer.models.OptionInfo)
        # param_decls are still specified in create_profile_parameter
        assert option.param_decls == ("--profile", "-p")
        assert option.help == "Keyboard profile in format 'keyboard' or 'keyboard/firmware'"
        assert option.autocompletion is not None

    def test_create_profile_parameter_required(self):
        """Test creating a required profile parameter."""
        param = ParameterFactory.create_profile_parameter(
            required=True
        )

        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg is str
        assert option.default == ...
        assert "(required)" in option.help

    def test_create_profile_parameter_with_default(self):
        """Test creating a profile parameter with default."""
        param = ParameterFactory.create_profile_parameter(
            default="glove80/v25.05",
            required=True
        )

        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg == str | None  # Has default, so nullable
        assert option.default == ...  # Default is in function signature
        assert "(required)" not in option.help  # Has default, so not truly required
        assert option.show_default is True


class TestLegacyCompatibility:
    """Test backward compatibility with legacy method names."""

    def test_legacy_input_file(self):
        """Test legacy input_file method still works."""
        param = ParameterFactory.input_file()

        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]

        from pathlib import Path
        assert type_arg == Path
        assert argument.help == "Input file path"
        assert argument.exists is True

    def test_legacy_output_file(self):
        """Test legacy output_file method still works."""
        param = ParameterFactory.output_file()

        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg == str | None
        assert option.param_decls == ("--output", "-o")
        assert "If not specified, generates a smart default filename" in option.help

    def test_legacy_output_file_with_stdout(self):
        """Test legacy output_file with stdout support."""
        param = ParameterFactory.output_file(supports_stdout=True)

        args = get_args(param)
        option = args[1]
        assert "Use '-' for stdout" in option.help

    def test_legacy_profile_option(self):
        """Test legacy profile_option method still works."""
        param = ParameterFactory.profile_option()

        assert get_origin(param) is Annotated
        args = get_args(param)
        option = args[1]

        assert option.param_decls == ("--profile", "-p")

    def test_legacy_json_file_argument(self):
        """Test legacy json_file_argument method still works."""
        param = ParameterFactory.json_file_argument()

        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]

        assert type_arg == str | None  # Changed to match implementation
        assert "JSON layout file" in argument.help
        assert "@library-name/uuid" in argument.help

    def test_legacy_force_overwrite(self):
        """Test legacy force_overwrite method still works."""
        param = ParameterFactory.force_overwrite()

        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg is bool
        assert option.param_decls == ("--force",)
        # Boolean default is typically False in function signature

    def test_legacy_output_format(self):
        """Test legacy output_format method still works."""
        param = ParameterFactory.output_format()

        assert get_origin(param) is Annotated
        args = get_args(param)
        type_arg = args[0]
        option = args[1]

        assert type_arg is str
        assert option.param_decls == ("--output-format", "-t")
        # Default is in function signature
        assert option.autocompletion is not None


class TestCommonParameterSets:
    """Test legacy CommonParameterSets still work."""

    def test_input_output_format_set(self):
        """Test input_output_format parameter set."""
        params = CommonParameterSets.input_output_format()

        expected_keys = {"input_file", "output", "output_format", "force"}
        assert set(params.keys()) == expected_keys

        # Verify each parameter is Annotated
        for param in params.values():
            assert get_origin(param) is Annotated

    def test_compilation_parameters_set(self):
        """Test compilation_parameters set."""
        params = CommonParameterSets.compilation_parameters()

        expected_keys = {"json_file", "output_dir", "profile", "force", "verbose"}
        assert set(params.keys()) == expected_keys

        # Verify JSON file has proper help text
        args = get_args(params["json_file"])
        argument = args[1]
        assert "JSON layout file" in argument.help

    def test_display_parameters_set(self):
        """Test display_parameters set."""
        params = CommonParameterSets.display_parameters()

        expected_keys = {"json_file", "output_format", "verbose"}
        assert set(params.keys()) == expected_keys

    def test_file_transformation_parameters_set(self):
        """Test file_transformation_parameters set."""
        params = CommonParameterSets.file_transformation_parameters()

        expected_keys = {"input_file", "output", "force", "backup", "dry_run"}
        assert set(params.keys()) == expected_keys

        # By default supports stdout
        args = get_args(params["output"])
        option = args[1]
        assert "'-' for stdout" in option.help

    def test_file_transformation_no_stdout(self):
        """Test file transformation without stdout support."""
        params = CommonParameterSets.file_transformation_parameters(
            supports_stdout=False
        )

        # Should not mention stdout
        args = get_args(params["output"])
        option = args[1]
        assert "'-' for stdout" not in option.help


class TestParameterCustomization:
    """Test parameter customization features."""

    def test_custom_help_texts(self):
        """Test that custom help texts work properly."""
        input_param = ParameterFactory.create_input_parameter(
            help_text="My custom input help"
        )
        args = get_args(input_param)
        assert args[1].help == "My custom input help"

        output_param = ParameterFactory.create_output_parameter(
            help_text="My custom output help"
        )
        args = get_args(output_param)
        assert args[1].help == "My custom output help"

        profile_param = ParameterFactory.create_profile_parameter(
            help_text="My custom profile help"
        )
        args = get_args(profile_param)
        assert args[1].help == "My custom profile help"

    def test_legacy_custom_help(self):
        """Test legacy methods accept custom help."""
        param = ParameterFactory.force_overwrite(
            help_text="Custom force help"
        )
        args = get_args(param)
        assert args[1].help == "Custom force help"

    def test_legacy_env_var_customization(self):
        """Test legacy methods handle env var customization."""
        param = ParameterFactory.input_file_optional(
            env_var="MY_CUSTOM_ENV"
        )
        args = get_args(param)
        assert "MY_CUSTOM_ENV" in args[1].help


class TestEdgeCases:
    """Test edge cases and special behaviors."""

    def test_json_completion_only_for_json_help(self):
        """Test autocompletion is only added when help mentions JSON."""
        json_param = ParameterFactory.create_input_parameter(
            help_text="JSON file input"
        )
        args = get_args(json_param)
        assert args[1].autocompletion is not None

        non_json_param = ParameterFactory.create_input_parameter(
            help_text="Regular file input"
        )
        args = get_args(non_json_param)
        assert args[1].autocompletion is None

    def test_show_default_behavior(self):
        """Test show_default is set based on default value."""
        # No default = no show_default
        param1 = ParameterFactory.create_input_parameter(required=True)
        args = get_args(param1)
        assert not args[1].show_default

        # Has default = show_default
        param2 = ParameterFactory.create_input_parameter(
            default="test.txt",
            required=False
        )
        args = get_args(param2)
        assert args[1].show_default

    def test_required_profile_without_default(self):
        """Test required profile adds (required) to help."""
        param = ParameterFactory.create_profile_parameter(required=True)
        args = get_args(param)
        assert "(required)" in args[1].help

    def test_required_profile_with_default(self):
        """Test required profile with default doesn't add (required)."""
        param = ParameterFactory.create_profile_parameter(
            required=True,
            default="glove80"
        )
        args = get_args(param)
        assert "(required)" not in args[1].help
