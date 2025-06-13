"""Test BuildMatrixResolver class."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from glovebox.compilation.configuration.build_matrix_resolver import (
    BuildMatrixResolver,
    BuildMatrixResolverError,
    create_build_matrix_resolver,
)
from glovebox.compilation.models.build_matrix import BuildMatrix, BuildTarget


class TestBuildMatrixResolver:
    """Test BuildMatrixResolver functionality."""

    def setup_method(self):
        """Set up test instance."""
        self.resolver = BuildMatrixResolver()

    def test_initialization(self):
        """Test resolver initialization."""
        assert hasattr(self.resolver, "logger")

    def test_create_build_matrix_resolver(self):
        """Test factory function."""
        resolver = create_build_matrix_resolver()
        assert isinstance(resolver, BuildMatrixResolver)

    def test_resolve_from_build_yaml_with_include(self):
        """Test build.yaml parsing with include entries."""
        build_config = {
            "include": [
                {"board": "nice_nano_v2", "shield": "corne_left"},
                {"board": "nice_nano_v2", "shield": "corne_right"},
                {"board": "seeeduino_xiao_ble"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert isinstance(result, BuildMatrix)
            assert len(result.targets) == 3

            # Check first target
            target1 = result.targets[0]
            assert target1.board == "nice_nano_v2"
            assert target1.shield == "corne_left"
            assert target1.artifact_name == "nice_nano_v2-corne_left"

            # Check second target
            target2 = result.targets[1]
            assert target2.board == "nice_nano_v2"
            assert target2.shield == "corne_right"
            assert target2.artifact_name == "nice_nano_v2-corne_right"

            # Check third target (no shield)
            target3 = result.targets[2]
            assert target3.board == "seeeduino_xiao_ble"
            assert target3.shield is None
            assert target3.artifact_name == "seeeduino_xiao_ble"

        finally:
            build_yaml_path.unlink()

    def test_resolve_from_build_yaml_with_board_shield_defaults(self):
        """Test build.yaml parsing with board/shield defaults."""
        build_config = {
            "board": ["nice_nano_v2", "seeeduino_xiao_ble"],
            "shield": ["corne_left", "corne_right"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert isinstance(result, BuildMatrix)
            assert len(result.targets) == 4  # 2 boards × 2 shields
            assert len(result.board_defaults) == 2
            assert len(result.shield_defaults) == 2

            # Check all combinations are present
            expected_combinations = [
                ("nice_nano_v2", "corne_left"),
                ("nice_nano_v2", "corne_right"),
                ("seeeduino_xiao_ble", "corne_left"),
                ("seeeduino_xiao_ble", "corne_right"),
            ]

            actual_combinations = [
                (target.board, target.shield) for target in result.targets
            ]

            for expected in expected_combinations:
                assert expected in actual_combinations

        finally:
            build_yaml_path.unlink()

    def test_resolve_from_build_yaml_board_only(self):
        """Test build.yaml parsing with board only."""
        build_config = {
            "board": ["nice_nano_v2", "seeeduino_xiao_ble"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert isinstance(result, BuildMatrix)
            assert len(result.targets) == 2

            # Check targets have no shields
            for target in result.targets:
                assert target.shield is None
                assert target.artifact_name == target.board

        finally:
            build_yaml_path.unlink()

    def test_resolve_from_build_yaml_include_with_cmake_args(self):
        """Test build.yaml parsing with cmake-args."""
        build_config = {
            "include": [
                {
                    "board": "nice_nano_v2",
                    "shield": "corne_left",
                    "cmake-args": ["-DCONFIG_ZMK_RGB_UNDERGLOW=y"],
                    "snippet": "zmk-config",
                    "artifact-name": "custom-corne-left",
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert len(result.targets) == 1
            target = result.targets[0]

            assert target.board == "nice_nano_v2"
            assert target.shield == "corne_left"
            assert target.cmake_args == ["-DCONFIG_ZMK_RGB_UNDERGLOW=y"]
            assert target.snippet == "zmk-config"
            assert target.artifact_name == "custom-corne-left"

        finally:
            build_yaml_path.unlink()

    def test_resolve_from_build_yaml_empty_file(self):
        """Test build.yaml parsing with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({}, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert isinstance(result, BuildMatrix)
            assert len(result.targets) == 0
            assert len(result.board_defaults) == 0
            assert len(result.shield_defaults) == 0

        finally:
            build_yaml_path.unlink()

    def test_resolve_from_build_yaml_file_not_found(self):
        """Test error handling for missing build.yaml file."""
        non_existent_path = Path("/non/existent/build.yaml")

        with pytest.raises(
            BuildMatrixResolverError, match="Failed to parse build.yaml"
        ):
            self.resolver.resolve_from_build_yaml(non_existent_path)

    def test_resolve_from_build_yaml_invalid_yaml(self):
        """Test error handling for invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            build_yaml_path = Path(f.name)

        try:
            with pytest.raises(
                BuildMatrixResolverError, match="Failed to parse build.yaml"
            ):
                self.resolver.resolve_from_build_yaml(build_yaml_path)
        finally:
            build_yaml_path.unlink()

    def test_process_include_entries_missing_board(self):
        """Test processing include entries with missing board."""
        include_entries = [
            {"shield": "corne_left"},  # Missing board
            {"board": "nice_nano_v2", "shield": "corne_right"},  # Valid
        ]

        with patch.object(self.resolver.logger, "warning") as mock_warning:
            targets = self.resolver._process_include_entries(include_entries)

        # Should only process the valid entry
        assert len(targets) == 1
        assert targets[0].board == "nice_nano_v2"
        assert targets[0].shield == "corne_right"

        # Should log warning for invalid entry
        mock_warning.assert_called_once_with(
            "Include entry missing board: %s", {"shield": "corne_left"}
        )

    def test_generate_default_combinations_boards_and_shields(self):
        """Test generating combinations from boards and shields."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            board=["board1", "board2"],
            shield=["shield1", "shield2"],
        )

        targets = self.resolver._generate_default_combinations(config)

        assert len(targets) == 4
        combinations = [(t.board, t.shield) for t in targets]
        expected = [
            ("board1", "shield1"),
            ("board1", "shield2"),
            ("board2", "shield1"),
            ("board2", "shield2"),
        ]

        for expected_combo in expected:
            assert expected_combo in combinations

    def test_generate_default_combinations_boards_only(self):
        """Test generating combinations from boards only."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            board=["board1", "board2"],
            shield=None,
        )

        targets = self.resolver._generate_default_combinations(config)

        assert len(targets) == 2
        assert all(t.shield is None for t in targets)
        boards = [t.board for t in targets]
        assert "board1" in boards
        assert "board2" in boards

    def test_generate_artifact_name_with_shield(self):
        """Test artifact name generation with shield."""
        target = BuildTarget(board="nice_nano_v2", shield="corne_left")

        artifact_name = self.resolver._generate_artifact_name(target)

        assert artifact_name == "nice_nano_v2-corne_left"

    def test_generate_artifact_name_without_shield(self):
        """Test artifact name generation without shield."""
        target = BuildTarget(board="nice_nano_v2")

        artifact_name = self.resolver._generate_artifact_name(target)

        assert artifact_name == "nice_nano_v2"

    def test_load_build_yaml_success(self):
        """Test successful YAML loading."""
        test_config = {"board": ["test_board"]}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(test_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver._load_build_yaml(build_yaml_path)
            assert result == test_config
        finally:
            build_yaml_path.unlink()

    def test_load_build_yaml_empty_file(self):
        """Test loading empty YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")  # Empty file
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver._load_build_yaml(build_yaml_path)
            assert result == {}
        finally:
            build_yaml_path.unlink()

    def test_resolve_from_config(self):
        """Test resolving build matrix from BuildYamlConfig instance."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            board=["nice_nano_v2"],
            shield=["corne_left", "corne_right"],
        )

        result = self.resolver.resolve_from_config(config)

        assert isinstance(result, BuildMatrix)
        assert len(result.targets) == 2
        assert len(result.board_defaults) == 1
        assert len(result.shield_defaults) == 2

        # Check targets
        combinations = [(t.board, t.shield) for t in result.targets]
        expected = [("nice_nano_v2", "corne_left"), ("nice_nano_v2", "corne_right")]

        for expected_combo in expected:
            assert expected_combo in combinations

    def test_resolve_from_config_with_include(self):
        """Test resolving build matrix from config with include entries."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            include=[
                {"board": "nice_nano_v2", "shield": "corne_left"},
                {"board": "seeeduino_xiao_ble"},
            ]
        )

        result = self.resolver.resolve_from_config(config)

        assert len(result.targets) == 2
        assert result.targets[0].board == "nice_nano_v2"
        assert result.targets[0].shield == "corne_left"
        assert result.targets[1].board == "seeeduino_xiao_ble"
        assert result.targets[1].shield is None

    def test_write_config_to_yaml(self):
        """Test writing BuildYamlConfig to YAML file."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            board=["nice_nano_v2", "seeeduino_xiao_ble"],
            shield=["corne_left", "corne_right"],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_build.yaml"

            self.resolver.write_config_to_yaml(config, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify contents
            with output_path.open(encoding="utf-8") as f:
                written_config = yaml.safe_load(f)

            assert written_config["board"] == ["nice_nano_v2", "seeeduino_xiao_ble"]
            assert written_config["shield"] == ["corne_left", "corne_right"]

    def test_write_config_to_yaml_with_include(self):
        """Test writing BuildYamlConfig with include entries to YAML file."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            include=[
                {"board": "nice_nano_v2", "shield": "corne_left"},
                {"board": "seeeduino_xiao_ble"},
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_build.yaml"

            self.resolver.write_config_to_yaml(config, output_path)

            # Verify file was created
            assert output_path.exists()

            # Verify contents
            with output_path.open(encoding="utf-8") as f:
                written_config = yaml.safe_load(f)

            assert len(written_config["include"]) == 2
            assert written_config["include"][0]["board"] == "nice_nano_v2"
            assert written_config["include"][0]["shield"] == "corne_left"
            assert written_config["include"][1]["board"] == "seeeduino_xiao_ble"

    def test_write_config_to_yaml_creates_directory(self):
        """Test that write_config_to_yaml creates parent directories."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(board=["test_board"])

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested path that doesn't exist
            output_path = Path(temp_dir) / "nested" / "dirs" / "test_build.yaml"

            self.resolver.write_config_to_yaml(config, output_path)

            # Verify file and directories were created
            assert output_path.exists()
            assert output_path.parent.exists()

    def test_write_config_to_yaml_excludes_none_values(self):
        """Test that None values are excluded from written YAML."""
        from glovebox.compilation.models.build_matrix import BuildYamlConfig

        config = BuildYamlConfig(
            board=["test_board"],
            shield=None,  # This should be excluded
            include=None,  # This should be excluded
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "test_build.yaml"

            self.resolver.write_config_to_yaml(config, output_path)

            # Verify contents exclude None values
            with output_path.open(encoding="utf-8") as f:
                written_config = yaml.safe_load(f)

            assert "board" in written_config
            assert "shield" not in written_config
            assert "include" not in written_config


class TestRealWorldScenarios:
    """Test with real-world ZMK build.yaml scenarios."""

    def setup_method(self):
        """Set up test instance."""
        self.resolver = BuildMatrixResolver()

    def test_corne_keyboard_build_yaml(self):
        """Test with realistic Corne keyboard build.yaml."""
        build_config = {
            "include": [
                {"board": "nice_nano_v2", "shield": "corne_left"},
                {"board": "nice_nano_v2", "shield": "corne_right"},
                {"board": "nice_nano_v2", "shield": "settings_reset"},
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert len(result.targets) == 3

            # Verify artifact names
            artifact_names = [t.artifact_name for t in result.targets]
            expected_names = [
                "nice_nano_v2-corne_left",
                "nice_nano_v2-corne_right",
                "nice_nano_v2-settings_reset",
            ]

            for expected_name in expected_names:
                assert expected_name in artifact_names

        finally:
            build_yaml_path.unlink()

    def test_glove80_build_yaml(self):
        """Test with Glove80-style build.yaml."""
        build_config = {
            "include": [
                {
                    "board": "glove80_lh",
                    "cmake-args": ["-DCONFIG_ZMK_RGB_UNDERGLOW=y"],
                },
                {
                    "board": "glove80_rh",
                    "cmake-args": ["-DCONFIG_ZMK_RGB_UNDERGLOW=y"],
                },
            ]
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(build_config, f)
            build_yaml_path = Path(f.name)

        try:
            result = self.resolver.resolve_from_build_yaml(build_yaml_path)

            assert len(result.targets) == 2

            for target in result.targets:
                assert target.cmake_args == ["-DCONFIG_ZMK_RGB_UNDERGLOW=y"]
                assert target.shield is None  # Glove80 doesn't use shields
                assert target.artifact_name in ["glove80_lh", "glove80_rh"]

        finally:
            build_yaml_path.unlink()
