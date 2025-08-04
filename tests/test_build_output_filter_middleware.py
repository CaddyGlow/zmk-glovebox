"""Tests for build output filter middleware."""

import logging
from unittest.mock import MagicMock

import pytest

from glovebox.utils.build_output_filter_middleware import (
    create_build_output_filter_middleware,
)


class TestBuildOutputFilterMiddleware:
    """Test suite for BuildOutputFilterMiddleware."""

    @pytest.fixture
    def mock_progress_context(self):
        """Create mock progress context."""
        context = MagicMock()
        context.log = MagicMock()
        return context

    @pytest.fixture
    def middleware(self, mock_progress_context):
        """Create middleware instance for testing."""
        return create_build_output_filter_middleware(mock_progress_context)

    def test_filter_verbose_macro_expansion(self, middleware):
        """Test filtering of verbose macro expansion notes."""
        # Verbose lines that should be filtered
        verbose_lines = [
            "/nix/store/xyz/devicetree.h:3247:27: note: in expansion of macro 'DT_INST'",
            "#define DT_FOREACH_OKAY_INST_zmk_behavior_mod_morph(fn) fn(0) fn(1) fn(2)",
            "#define UTIL_PRIMITIVE_CAT(a, ...) a##__VA_ARGS__",
            "/tmp/nix-build-zmk.drv-0/source/app.c:96:17: note: in definition of macro 'DT_INST_PROP'",
        ]

        for line in verbose_lines:
            result = middleware.process(line, "stderr")
            assert result == "", f"Should filter: {line}"

        # Check statistics
        stats = middleware.get_statistics()
        assert stats["filtered_lines"] == len(verbose_lines)
        assert stats["preserved_lines"] == 0

    def test_preserve_important_warnings(self, middleware):
        """Test preservation of important warnings."""
        important_lines = [
            'warning: "ZMK_POINTING_DEFAULT_MOVE_VAL" redefined',
            "'label' is marked as deprecated in 'properties:' for node /behaviors/lower",
            "warning: 'rgb_underglow_auto_state' defined but not used",
            "error: compilation failed",
            "ERROR: Docker subprocess error",
        ]

        for line in important_lines:
            result = middleware.process(line, "stderr")
            assert result == line, f"Should preserve: {line}"

        # Check statistics
        stats = middleware.get_statistics()
        assert stats["preserved_lines"] == len(important_lines)
        assert stats["filtered_lines"] == 0

    def test_overflow_warning_block_filtering(self, middleware):
        """Test filtering of overflow warning blocks."""
        # Overflow warning block that should be filtered
        lines = [
            "warning: unsigned conversion from 'long long int' to 'unsigned char' changes value from '4294967292' to '252'",
            "   96 |         .mods = DT_INST_PROP(n, mods),",
            "      |                 ^~~~~~~~~~~~",
            "/nix/store/xyz.h:105:36: note: in expansion of macro 'DT_FOREACH_OKAY_INST'",
        ]

        for line in lines:
            result = middleware.process(line, "stderr")
            assert result == "", f"Should filter overflow block: {line}"

        stats = middleware.get_statistics()
        assert stats["filtered_lines"] == len(lines)

    def test_multi_line_macro_expansion_filtering(self, middleware):
        """Test filtering of multi-line macro expansion warnings."""
        # These lines with line numbers are NOT filtered anymore since we want to preserve
        # code context for important warnings. They would only be filtered if preceded
        # by a verbose warning trigger.

        # Start with an overflow warning to trigger verbose block
        trigger = "warning: unsigned conversion from 'long long int' to 'unsigned char' changes value from '4294967292' to '252'"
        result = middleware.process(trigger, "stderr")
        assert result == ""  # This triggers verbose block

        # Now these should be filtered as part of the verbose block
        lines = [
            "   64 |         __GET_ARG2_DEBRACKET(one_or_two_args _if_code, _else_code)",
            "      |         ^~~~~~~~~~~~~~~~~~~~",
            "",
            "   61 |         __COND_CODE(_ZZZZ##_flag, _if_0_code, _else_code)",
            "      |         ^~~~~~~~~~~",
        ]

        for line in lines:
            result = middleware.process(line, "stderr")
            assert result == "", f"Should filter in verbose block: {line}"

    def test_blank_line_management(self, middleware):
        """Test that blank lines are managed correctly."""
        # Process: normal line, blank, filtered, blank, normal
        result1 = middleware.process("Normal line 1", "stdout")
        assert result1 == "Normal line 1"

        result2 = middleware.process("", "stdout")  # Blank line
        assert result2 == ""  # Normal blank preserved

        result3 = middleware.process(
            "/nix/store/xyz.h:1:1: note: in expansion of macro", "stderr"
        )
        assert result3 == ""  # Filtered

        result4 = middleware.process("", "stdout")  # Blank after filtered
        assert result4 == ""  # Should be buffered

        result5 = middleware.process("Normal line 2", "stdout")
        # Should output buffered blank + normal line
        assert "Normal line 2" in result5

    def test_mixed_content(self, middleware):
        """Test handling of mixed verbose and important content."""
        sequence = [
            ("Building firmware...", "stdout", True),  # Should preserve
            ("", "stdout", True),  # Blank line
            (
                "warning: unsigned conversion from 'long long int' to 'unsigned char' changes value from '4294967292' to '252'",
                "stderr",
                False,
            ),  # Filter - starts verbose block
            (
                "   64 | some code here",
                "stderr",
                False,
            ),  # Filter - part of verbose block
            ("", "stdout", False),  # Blank after filtered - should be removed
            ('warning: "CONFIG_VALUE" redefined', "stderr", True),  # Important
            ("Compilation complete", "stdout", True),  # Normal
        ]

        for line, stream, should_preserve in sequence:
            result = middleware.process(line, stream)
            if should_preserve:
                assert line in result or result == line, f"Should preserve: {line}"
            else:
                assert result == "", f"Should filter: {line}"

    def test_statistics_tracking(self, middleware):
        """Test that statistics are tracked correctly."""
        # Process some lines
        middleware.process("Normal line", "stdout")
        middleware.process(
            "/nix/store/xyz.h:1:1: note: in expansion of macro TEST", "stderr"
        )  # This should be filtered
        middleware.process("error: failed", "stderr")
        middleware.process(
            "#define DT_INST(x)", "stderr"
        )  # This will be preserved as context

        stats = middleware.get_statistics()
        assert (
            stats["preserved_lines"] == 3
        )  # Normal + error + context line after error
        assert stats["filtered_lines"] == 1  # One verbose line (note: in expansion)
        assert stats["total_lines"] == 4

    def test_important_warning_preserves_context(self, middleware):
        """Test that important warnings preserve their context lines (pointer lines)."""
        lines = [
            'warning: "ZMK_POINTING_DEFAULT_MOVE_VAL" redefined',  # Important warning
            "11026 |   #define ZMK_POINTING_DEFAULT_MOVE_VAL MOUSE_MOTION_MAXIMUM_SPEED",  # Context line
            "      |",  # Line with just pipe (actual case from output)
            "",  # Blank line
            "Normal output continues here",
        ]

        results = []
        for line in lines:
            result = middleware.process(line, "stderr")
            results.append(result)

        # First line (important warning) should be preserved
        assert results[0] == lines[0]
        # Context lines after important warning should be preserved
        assert results[1] == lines[1]  # Code line
        assert results[2] == lines[2]  # Separator line
        assert results[3] == lines[3]  # Blank line preserved
        assert results[4] == lines[4]  # Normal line

    def test_redefined_warning_with_note(self, middleware):
        """Test realistic redefined warning output with note about previous definition."""
        lines = [
            "In file included from <command-line>:",
            '/config/glove80.keymap:11026: warning: "ZMK_POINTING_DEFAULT_MOVE_VAL" redefined',
            "11026 |   #define ZMK_POINTING_DEFAULT_MOVE_VAL MOUSE_MOTION_MAXIMUM_SPEED",
            "      |",
            "In file included from /config/glove80.keymap:20:",
            "/app/include/dt-bindings/zmk/pointing.h:27: note: this is the location of the previous definition",
            "   27 | #define ZMK_POINTING_DEFAULT_MOVE_VAL 600",
            "      |",
        ]

        results = []
        for line in lines:
            result = middleware.process(line, "stderr")
            results.append(result)

        # Check that important warning and its context are preserved
        assert 'warning: "ZMK_POINTING_DEFAULT_MOVE_VAL" redefined' in results[1]
        # The next 5 lines should be preserved as context
        for i in range(2, 7):
            assert results[i] == lines[i], f"Line {i} should be preserved as context"

    def test_unused_function_warning_with_context(self, middleware):
        """Test that 'defined but not used' warnings preserve their code context."""
        lines = [
            "/tmp/nix-build-zmk_glove80_lh.drv-0/source/app/src/rgb_underglow.c:923:12: warning: 'rgb_underglow_auto_state' defined but not used [-Wunused-function]",
            "  923 | static int rgb_underglow_auto_state(bool target_wake_state) {",
            "      |            ^~~~~~~~~~~~~~~~~~~~~~~~",
            "",
            "Normal compilation continues",
        ]

        results = []
        for line in lines:
            result = middleware.process(line, "stderr")
            results.append(result)

        # Warning should be preserved
        assert "defined but not used" in results[0]
        # Context lines should be preserved
        assert results[1] == lines[1]  # Code line with line number
        assert results[2] == lines[2]  # Pointer line
        assert results[3] == lines[3]  # Blank
        assert results[4] == lines[4]  # Normal line

    def test_close_logs_statistics(self, middleware, mock_progress_context, caplog):
        """Test that close() logs statistics."""
        # Process some lines to generate statistics
        for _ in range(150):
            middleware.process(
                "/nix/store/xyz.h:1:1: note: in expansion of macro", "stderr"
            )

        middleware.process("Normal line", "stdout")

        with caplog.at_level(logging.DEBUG):
            middleware.close()

        # Check that statistics were logged
        assert "Build output filter statistics" in caplog.text
        assert "150" in caplog.text  # Filtered count

        # Check progress context was updated
        mock_progress_context.log.assert_called()
