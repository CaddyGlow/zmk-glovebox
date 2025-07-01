"""Tests for CLI parameter factory."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_args, get_origin

import pytest
import typer
from typing_extensions import Annotated

from glovebox.cli.helpers.parameter_factory import (
    ParameterFactory,
    CommonParameterSets,
)


# =============================================================================
# Test Output Parameter Factories
# =============================================================================

class TestOutputParameterFactories:
    """Test output parameter factory methods."""

    def test_output_file_basic(self):
        """Test basic output file parameter creation."""
        param = ParameterFactory.output_file()
        
        # Verify it's an Annotated type
        assert get_origin(param) is Annotated
        args = get_args(param)
        assert len(args) == 2
        
        # Check the type
        type_arg = args[0]
        assert type_arg == str | None
        
        # Check the typer.Option
        option = args[1]
        assert isinstance(option, typer.Option)
        assert option.param_decls == ("--output", "-o")
        assert "Output file path" in option.help

    def test_output_file_with_stdout(self):
        """Test output file parameter with stdout support."""
        param = ParameterFactory.output_file(supports_stdout=True)
        
        args = get_args(param)
        option = args[1]
        assert "'-' for stdout" in option.help

    def test_output_file_custom_help(self):
        """Test output file parameter with custom help text."""
        custom_help = "Custom output file help"
        param = ParameterFactory.output_file(help_text=custom_help)
        
        args = get_args(param)
        option = args[1]
        assert option.help == custom_help

    def test_output_file_path_only(self):
        """Test output file parameter (Path type only)."""
        param = ParameterFactory.output_file_path_only()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == Path | None
        assert option.dir_okay is False
        assert option.writable is True

    def test_output_directory(self):
        """Test output directory parameter creation."""
        param = ParameterFactory.output_directory()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == Path
        assert option.file_okay is False
        assert option.dir_okay is True
        assert option.writable is True

    def test_output_directory_optional(self):
        """Test optional output directory parameter creation."""
        param = ParameterFactory.output_directory_optional()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == Path | None
        assert "current directory" in option.help


# =============================================================================
# Test Input Parameter Factories
# =============================================================================

class TestInputParameterFactories:
    """Test input parameter factory methods."""

    def test_input_file_basic(self):
        """Test basic input file parameter creation."""
        param = ParameterFactory.input_file()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == Path
        assert isinstance(argument, typer.Argument)
        assert argument.exists is True
        assert argument.file_okay is True
        assert argument.dir_okay is False
        assert argument.readable is True

    def test_input_file_with_extensions(self):
        """Test input file parameter with extension information."""
        extensions = [".json", ".yaml"]
        param = ParameterFactory.input_file(file_extensions=extensions)
        
        args = get_args(param)
        argument = args[1]
        
        assert ".json, .yaml" in argument.help

    def test_input_file_optional(self):
        """Test optional input file parameter creation."""
        param = ParameterFactory.input_file_optional()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == Path | None
        assert argument.exists is False  # Will be validated later
        assert "GLOVEBOX_JSON_FILE" in argument.help

    def test_input_file_optional_custom_env(self):
        """Test optional input file with custom environment variable."""
        param = ParameterFactory.input_file_optional(env_var="CUSTOM_ENV")
        
        args = get_args(param)
        argument = args[1]
        
        assert "CUSTOM_ENV" in argument.help

    def test_input_file_with_stdin(self):
        """Test input file parameter with stdin support."""
        param = ParameterFactory.input_file_with_stdin()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == str
        assert "'-' for stdin" in argument.help

    def test_input_file_with_stdin_optional(self):
        """Test optional input file parameter with stdin support."""
        param = ParameterFactory.input_file_with_stdin_optional()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == str | None
        assert "'-' for stdin" in argument.help
        assert "GLOVEBOX_JSON_FILE" in argument.help

    def test_input_directory(self):
        """Test input directory parameter creation."""
        param = ParameterFactory.input_directory()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == Path
        assert argument.exists is True
        assert argument.file_okay is False
        assert argument.dir_okay is True
        assert argument.readable is True

    def test_input_multiple_files(self):
        """Test multiple input files parameter creation."""
        param = ParameterFactory.input_multiple_files()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == list[Path]
        assert argument.exists is True
        assert argument.file_okay is True
        assert argument.dir_okay is False

    def test_input_multiple_files_with_extensions(self):
        """Test multiple input files with extension information."""
        extensions = [".json", ".yaml"]
        param = ParameterFactory.input_multiple_files(file_extensions=extensions)
        
        args = get_args(param)
        argument = args[1]
        
        assert ".json, .yaml" in argument.help

    def test_json_file_argument(self):
        """Test JSON file argument creation."""
        param = ParameterFactory.json_file_argument()
        
        args = get_args(param)
        type_arg = args[0]
        argument = args[1]
        
        assert type_arg == str | None
        assert "JSON layout file" in argument.help
        assert "'-' for stdin" in argument.help
        assert "GLOVEBOX_JSON_FILE" in argument.help
        assert argument.autocompletion is not None


# =============================================================================
# Test Format Parameter Factories
# =============================================================================

class TestFormatParameterFactories:
    """Test format parameter factory methods."""

    def test_output_format_basic(self):
        """Test basic output format parameter creation."""
        param = ParameterFactory.output_format()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == str
        assert isinstance(option, typer.Option)
        assert option.param_decls == ("--output-format", "-t")
        assert "rich-table|text|json|markdown" in option.help
        assert option.autocompletion is not None

    def test_output_format_custom_formats(self):
        """Test output format parameter with custom formats."""
        custom_formats = ["xml", "csv", "yaml"]
        param = ParameterFactory.output_format(supported_formats=custom_formats)
        
        args = get_args(param)
        option = args[1]
        
        assert "xml|csv|yaml" in option.help

    def test_legacy_format(self):
        """Test legacy format parameter creation."""
        param = ParameterFactory.legacy_format()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--format", "-f")
        assert "table|text|json|markdown" in option.help

    def test_json_boolean_flag(self):
        """Test JSON boolean flag parameter creation."""
        param = ParameterFactory.json_boolean_flag()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == bool
        assert option.param_decls == ("--json",)
        assert "JSON format" in option.help

    def test_format_with_json_flag(self):
        """Test format parameter with separate JSON flag."""
        param = ParameterFactory.format_with_json_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--format", "-f")
        assert "use --json for JSON format" in option.help


# =============================================================================
# Test Control Parameter Factories
# =============================================================================

class TestControlParameterFactories:
    """Test control parameter factory methods."""

    def test_force_overwrite(self):
        """Test force overwrite parameter creation."""
        param = ParameterFactory.force_overwrite()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == bool
        assert option.param_decls == ("--force",)
        assert "Overwrite existing files" in option.help

    def test_verbose_flag(self):
        """Test verbose flag parameter creation."""
        param = ParameterFactory.verbose_flag()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == bool
        assert option.param_decls == ("--verbose", "-v")
        assert "verbose output" in option.help

    def test_quiet_flag(self):
        """Test quiet flag parameter creation."""
        param = ParameterFactory.quiet_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--quiet", "-q")
        assert "Suppress non-error output" in option.help

    def test_dry_run_flag(self):
        """Test dry run flag parameter creation."""
        param = ParameterFactory.dry_run_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--dry-run",)
        assert "without making changes" in option.help

    def test_backup_flag(self):
        """Test backup flag parameter creation."""
        param = ParameterFactory.backup_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--backup",)
        assert "Create backup" in option.help

    def test_no_backup_flag(self):
        """Test no-backup flag parameter creation."""
        param = ParameterFactory.no_backup_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--no-backup",)
        assert "Do not create backup" in option.help

    def test_custom_help_text(self):
        """Test parameter creation with custom help text."""
        custom_help = "Custom help text for this parameter"
        param = ParameterFactory.force_overwrite(help_text=custom_help)
        
        args = get_args(param)
        option = args[1]
        
        assert option.help == custom_help

    def test_help_suffix(self):
        """Test parameter creation with help suffix."""
        suffix = " (use with caution)"
        param = ParameterFactory.dry_run_flag(default_help_suffix=suffix)
        
        args = get_args(param)
        option = args[1]
        
        assert option.help.endswith(suffix)


# =============================================================================
# Test Profile Parameter Factories
# =============================================================================

class TestProfileParameterFactories:
    """Test profile parameter factory methods."""

    def test_profile_option_optional(self):
        """Test optional profile parameter creation."""
        param = ParameterFactory.profile_option()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == str | None
        assert option.param_decls == ("--profile", "-p")
        assert "keyboard/firmware" in option.help
        assert "(required)" not in option.help
        assert option.autocompletion is not None

    def test_profile_option_required(self):
        """Test required profile parameter creation."""
        param = ParameterFactory.profile_option(required=True)
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == str
        assert "(required)" in option.help


# =============================================================================
# Test Validation Parameter Factories
# =============================================================================

class TestValidationParameterFactories:
    """Test validation parameter factory methods."""

    def test_validate_only_flag(self):
        """Test validate-only flag parameter creation."""
        param = ParameterFactory.validate_only_flag()
        
        args = get_args(param)
        type_arg = args[0]
        option = args[1]
        
        assert type_arg == bool
        assert option.param_decls == ("--validate-only",)
        assert "validate input without processing" in option.help

    def test_skip_validation_flag(self):
        """Test skip-validation flag parameter creation."""
        param = ParameterFactory.skip_validation_flag()
        
        args = get_args(param)
        option = args[1]
        
        assert option.param_decls == ("--skip-validation",)
        assert "Skip input validation" in option.help
        assert "use with caution" in option.help


# =============================================================================
# Test Common Parameter Sets
# =============================================================================

class TestCommonParameterSets:
    """Test pre-defined parameter sets."""

    def test_input_output_format_basic(self):
        """Test basic input/output/format parameter set."""
        params = CommonParameterSets.input_output_format()
        
        # Check that all expected parameters are present
        expected_keys = {"input_file", "output", "output_format", "force"}
        assert set(params.keys()) == expected_keys
        
        # Verify types
        for param_name, param_type in params.items():
            assert get_origin(param_type) is Annotated
            args = get_args(param_type)
            assert len(args) == 2

    def test_input_output_format_with_stdin_stdout(self):
        """Test input/output/format set with stdin/stdout support."""
        params = CommonParameterSets.input_output_format(
            supports_stdin=True,
            supports_stdout=True,
        )
        
        # Check input file type (should be str for stdin support)
        input_args = get_args(params["input_file"])
        input_type = input_args[0]
        assert input_type == str
        
        # Check that help text mentions stdin/stdout
        input_arg = input_args[1]
        assert "'-' for stdin" in input_arg.help

    def test_input_output_format_without_stdin(self):
        """Test input/output/format set without stdin support."""
        params = CommonParameterSets.input_output_format(
            supports_stdin=False,
        )
        
        # Check input file type (should be Path for file-only support)
        input_args = get_args(params["input_file"])
        input_type = input_args[0]
        assert input_type == Path

    def test_input_output_format_custom_help(self):
        """Test input/output/format set with custom help text."""
        custom_input_help = "Custom input help"
        custom_output_help = "Custom output help"
        custom_format_help = "Custom format help"
        
        params = CommonParameterSets.input_output_format(
            input_help=custom_input_help,
            output_help=custom_output_help,
            format_help=custom_format_help,
        )
        
        # Check custom help is used
        input_args = get_args(params["input_file"])
        output_args = get_args(params["output"])
        format_args = get_args(params["output_format"])
        
        assert input_args[1].help == custom_input_help
        assert output_args[1].help == custom_output_help
        assert format_args[1].help == custom_format_help

    def test_compilation_parameters(self):
        """Test compilation parameter set."""
        params = CommonParameterSets.compilation_parameters()
        
        expected_keys = {"json_file", "output_dir", "profile", "force", "verbose"}
        assert set(params.keys()) == expected_keys
        
        # Check JSON file has autocompletion
        json_args = get_args(params["json_file"])
        json_arg = json_args[1]
        assert json_arg.autocompletion is not None
        
        # Check output directory is optional
        output_args = get_args(params["output_dir"])
        output_type = output_args[0]
        assert output_type == Path | None

    def test_display_parameters(self):
        """Test display parameter set."""
        params = CommonParameterSets.display_parameters()
        
        expected_keys = {"json_file", "output_format", "verbose"}
        assert set(params.keys()) == expected_keys
        
        # Check format parameter has completion
        format_args = get_args(params["output_format"])
        format_option = format_args[1]
        assert format_option.autocompletion is not None

    def test_display_parameters_custom_formats(self):
        """Test display parameters with custom format types."""
        custom_formats = ["xml", "csv"]
        params = CommonParameterSets.display_parameters(
            format_types=custom_formats,
        )
        
        format_args = get_args(params["output_format"])
        format_option = format_args[1]
        assert "xml|csv" in format_option.help

    def test_file_transformation_parameters(self):
        """Test file transformation parameter set."""
        params = CommonParameterSets.file_transformation_parameters()
        
        expected_keys = {"input_file", "output", "force", "backup", "dry_run"}
        assert set(params.keys()) == expected_keys
        
        # Check input supports stdin
        input_args = get_args(params["input_file"])
        input_type = input_args[0]
        assert input_type == str
        
        # Check output supports stdout by default
        output_args = get_args(params["output"])
        output_type = output_args[0]
        assert output_type == str | None

    def test_file_transformation_parameters_no_stdout(self):
        """Test file transformation parameters without stdout support."""
        params = CommonParameterSets.file_transformation_parameters(
            supports_stdout=False,
        )
        
        # Check output doesn't support stdout
        output_args = get_args(params["output"])
        output_type = output_args[0]
        assert output_type == Path | None


# =============================================================================
# Test Parameter Type Consistency
# =============================================================================

class TestParameterTypeConsistency:
    """Test consistency of parameter types across factory methods."""

    def test_output_file_parameter_consistency(self):
        """Test that all output file parameters have consistent structure."""
        output_params = [
            ParameterFactory.output_file(),
            ParameterFactory.output_file_path_only(),
        ]
        
        for param in output_params:
            args = get_args(param)
            option = args[1]
            
            # All should be typer.Option with --output/-o
            assert isinstance(option, typer.Option)
            assert "--output" in option.param_decls
            assert "-o" in option.param_decls

    def test_input_file_parameter_consistency(self):
        """Test that all input file parameters have consistent structure."""
        input_params = [
            ParameterFactory.input_file(),
            ParameterFactory.input_directory(),
        ]
        
        for param in input_params:
            args = get_args(param)
            argument = args[1]
            
            # All should be typer.Argument with readable=True
            assert isinstance(argument, typer.Argument)
            assert argument.readable is True

    def test_format_parameter_consistency(self):
        """Test that format parameters have consistent structure."""
        format_params = [
            ParameterFactory.output_format(),
            ParameterFactory.legacy_format(),
        ]
        
        for param in format_params:
            args = get_args(param)
            type_arg = args[0]
            option = args[1]
            
            # All should be str type with typer.Option
            assert type_arg == str
            assert isinstance(option, typer.Option)
            assert option.autocompletion is not None

    def test_boolean_flag_consistency(self):
        """Test that boolean flags have consistent structure."""
        boolean_params = [
            ParameterFactory.force_overwrite(),
            ParameterFactory.verbose_flag(),
            ParameterFactory.quiet_flag(),
            ParameterFactory.dry_run_flag(),
        ]
        
        for param in boolean_params:
            args = get_args(param)
            type_arg = args[0]
            option = args[1]
            
            # All should be bool type with typer.Option
            assert type_arg == bool
            assert isinstance(option, typer.Option)


# =============================================================================
# Test Factory Usage Patterns
# =============================================================================

class TestFactoryUsagePatterns:
    """Test realistic factory usage patterns."""

    def test_command_definition_pattern(self):
        """Test using factory methods to define a command."""
        # Simulate defining a command with factory parameters
        def example_command(
            input_file: ParameterFactory.input_file_with_stdin(),
            output: ParameterFactory.output_file(supports_stdout=True),
            output_format: ParameterFactory.output_format(),
            force: ParameterFactory.force_overwrite(),
            verbose: ParameterFactory.verbose_flag(),
        ):
            """Example command using factory parameters."""
            return "success"
        
        # Get function signature
        sig = inspect.signature(example_command)
        
        # Verify all parameters are properly annotated
        for param_name, param in sig.parameters.items():
            assert param.annotation is not param.empty
            assert get_origin(param.annotation) is Annotated

    def test_parameter_customization_pattern(self):
        """Test customizing factory parameters."""
        # Create customized parameters
        custom_input = ParameterFactory.input_file(
            help_text="Custom input file help",
            file_extensions=[".json", ".yaml"],
        )
        
        custom_output = ParameterFactory.output_file(
            help_text="Custom output file help",
            supports_stdout=True,
        )
        
        # Verify customizations are applied
        input_args = get_args(custom_input)
        output_args = get_args(custom_output)
        
        assert input_args[1].help == "Custom input file help"
        assert output_args[1].help == "Custom output file help"
        assert "'-' for stdout" in output_args[1].help

    def test_parameter_set_usage_pattern(self):
        """Test using pre-defined parameter sets."""
        # Get a parameter set
        params = CommonParameterSets.input_output_format(
            input_help="Process this input file",
            output_help="Write output here",
            supports_stdin=True,
            supports_stdout=True,
        )
        
        # Simulate using the parameter set in a command
        def process_command(**kwargs):
            # Command would use the parameters
            return len(kwargs)
        
        # Verify parameter set can be used
        result = process_command(**{k: None for k in params.keys()})
        assert result == 4  # 4 parameters in the set

    def test_mixed_factory_and_manual_parameters(self):
        """Test mixing factory parameters with manual ones."""
        # Mix factory parameters with manual typer parameters
        def mixed_command(
            input_file: ParameterFactory.input_file(),
            output: ParameterFactory.output_file(),
            custom_param: str = typer.Option("default", help="Custom parameter"),
            count: int = typer.Option(1, help="Number of iterations"),
        ):
            """Command mixing factory and manual parameters."""
            return "mixed"
        
        # Verify signature is valid
        sig = inspect.signature(mixed_command)
        assert len(sig.parameters) == 4
        
        # Check factory parameters
        for param_name in ["input_file", "output"]:
            param = sig.parameters[param_name]
            assert get_origin(param.annotation) is Annotated